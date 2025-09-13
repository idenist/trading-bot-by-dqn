from datetime import datetime, timedelta
from math import floor, sqrt, log10, log1p
import random
from collections import deque

from sympy import limit

from stock_database import DBInteractor, CSVInteractor


def get_moving_avg(data, alpha=1.0, length=20, stddev_factor=None):
    if stddev_factor is None:
        stddev_factor = [0]
    if len(data) < length:
        data = [0] * (length - len(data)) + data
    elif len(data) > length:
        data = data[-length:]
    m_avg = 0
    if alpha == 1.0:
        m_avg = sum(data) / length
    else:
        for i in range(1, length):
            m_avg = alpha * m_avg + data[i] * (1 - alpha)
    avg = sum(data) / length
    var = sum([(x - avg) ** 2 for x in data]) / length
    return [m_avg + x * sqrt(var) for x in stddev_factor]


def get_rsi(data, length=14):
    au, ad = 0, 0
    if len(data) < length:
        data = [0] * (length - len(data) + 1) + data
    elif len(data) > length:
        data = data[-(length + 1):]
    for i in range(1, length):
        delta = data[i] - data[i - 1]
        if delta >= 0:
            au += delta
        else:
            ad -= delta
    if au + ad == 0:
        return 0.5
    return au / (au + ad)


def sample_interval(start: datetime, end: datetime, length=300):
    delta = end - start
    if delta.days < length:
        raise ValueError("End date must be at least 300 days after start date.")

    max_start_offset = delta.days - length
    random_start_offset = random.randint(0, max_start_offset)
    random_start = start + timedelta(days=random_start_offset)
    random_end = random_start + timedelta(days=length)

    return random_start, random_end

def min_max_norm(minimum, maximum, x):
    return ((x - minimum) / (maximum - minimum)) if maximum != minimum else 0.5


class StockEmulator:
    # constant
    PRICE_CACHE_SIZE = 120
    STATE_SIZE = 13
    ACTION_SIZE = 3
    TABLE_NAME = "STOCK_PRICES"
    LOG_STRUCTURE = [
        "Date",
        "Open",
        "Close",
        "High",
        "Low",
        "Bollinger_lower",
        "Bollinger_upper",
        "Moving_avg_20",
        "Moving_avg_60",
        "Moving_avg_120",
        "RSI_14",
        "Volume",
        "Position_value",
        "Avg_bought_price",
        "Action"
    ]

    @classmethod
    def get_state_dict(cls, data=None) -> dict:
        if data is None:
            return {x: [] for x in cls.LOG_STRUCTURE}
        tmp = {}
        for i in range(len(cls.LOG_STRUCTURE)):
            tmp[cls.LOG_STRUCTURE[i]] = data[i]
        return tmp

    def __init__(self, cash=10000, batch_size=1000, limit_train_domain=300, interval_length=300, ticker_exclusion=None):
        """
        :param cash: Initial money or seed money
        :param batch_size: Amount of data to pool
        :param limit_train_domain: Limit date range when fetching data.
        :param interval_length: Sample interval length.
        :param ticker_exclusion: Exclude ticker when choosing ticker at each initiate() call.
        :param timestep_skip:
        """
        # Connect DB
        self.db = DBInteractor(DBInteractor.DEFAULT_CFG)
        self.db.connect()
        # Account info
        self.seed_money = cash
        self.hold = 0
        self.cash = self.seed_money
        self.avg_price = 0
        self.estimated = self.seed_money
        # State info
        self.state_pool = None
        self.price_cache = None
        # DB fetch info
        self.ticker = None
        self.batch_size = batch_size
        self.batch_index = 0
        self.rows_left = 0
        self.cached = None
        # Randomize parameters
        self.limit_train_domain = limit_train_domain
        self.interval_length = interval_length
        self.ticker_exclusion = ticker_exclusion

        # fetch
        self.cached = None
        self.current_index = 0
        self.interval = (None, None)

    def sample_random_interval(self, sample_space):
        start = random.randint(self.limit_train_domain, sample_space - self.interval_length)
        return start, start + self.interval_length

    def reset(self, ticker=None, pooling=1, interval=None):
        # Validate input params
        if ticker is not None:
            assert ticker in self.db.fetch_tickers(self.TABLE_NAME)\
                , f"No ticker '{ticker}' in table {self.TABLE_NAME}."
        else:
            if self.ticker_exclusion is None:
                ticker = random.choice(list(set(self.db.fetch_tickers(self.TABLE_NAME))))
            else:
                ticker = random.choice(list(set(self.db.fetch_tickers(self.TABLE_NAME)).difference(set(self.ticker_exclusion))))
        assert pooling > 0, "Pooling must be greater than 0."
        # Initialize inner state
        # Account info
        self.hold = 0
        self.cash = self.seed_money
        self.avg_price = 0
        self.estimated = self.seed_money
        # State info
        self.state_pool = deque([], pooling)
        self.price_cache = deque([], 120)
        # DB fetch info
        self.ticker = ticker
        self.batch_index = 0
        self.cached = None
        # Query db
        if interval is None:
            interval = random.randint(self.limit_train_domain, self.db.get_data_amount(self.TABLE_NAME, ticker) - self.interval_length), self.interval_length
        self.rows_left = self.db.fetch_data_batch(self.TABLE_NAME, ticker, interval[0], interval[1])
        return [self.step(0)[0][0] for _ in range(pooling)]

    def next_row(self):
        self.batch_index += 1
        self.rows_left -= 1
        # print(self.batch_index, self.rows_left, len(self.cached) if self.cached is not None else -1)
        if self.cached is None or self.batch_index == self.batch_size:
            self.batch_index = 0
            self.cached = self.db.get_next_batch(self.batch_size)
        elif len(self.cached) <= self.batch_index:
            assert self.rows_left == 0, f"Error detected\nCache: {self.cached[0]}, ... {len(self.cached)} items.\nBatch_index: {self.batch_index}"
        if self.rows_left == 0:
            self.db.unlock()
        return self.cached[self.batch_index], self.rows_left == 0

    def step(self, action) -> tuple[list, int, bool, dict]:
        """
        Returns next state. Values are normalized.
        :param action:
        :param interval:
        :return: quadruple of (state, reward, end, raw)
        state : [open, close, high, low, bollinger_lower, bollinger_upper,
            moving_avg_20, moving_avg_60, moving_avg_120, 1 / volume, position_value, avg_bought_price]
        reward : Reward based on estimated value change rate
        end : True if interval finished
        raw : Data before normalize.
        """
        row, end = self.next_row()
        open, close, high, low, volume = map(float, row[2:])
        self.price_cache.append(close)
        price_cache_list = list(self.price_cache)
        reward, hold_change = self.update_state(close, action)
        local_max, local_min = max(price_cache_list[-100:]), min(price_cache_list[-100:])
        normalized_price = list(
            map(lambda x: ((x - local_min) / (local_max - local_min)) if local_min != local_max else 0.5, (open, close, high, low)))
        avg_index = (
                get_moving_avg(price_cache_list, stddev_factor=[-2, 2, 0])
                + get_moving_avg(price_cache_list, alpha=0.1, length=60)
                + get_moving_avg(price_cache_list, alpha=0.1, length=120)
        )
        state = (
                normalized_price
                + [x / (close * 2) for x in avg_index]
                + [get_rsi(price_cache_list, length=14), 1 / log10(volume)]
                + [self.estimated / (self.seed_money * 2), self.avg_price / (close * 2)]
        )
        raw_data = StockEmulator.get_state_dict(
            [row[0], open, close, high, low]
            + avg_index
            + [get_rsi(price_cache_list, 14), volume]
            + [self.estimated, self.avg_price, hold_change]
        )
        self.state_pool.append(state)
        return list(self.state_pool), reward, end, raw_data

    def update_state(self, reference_price, action):
        if action > 0:
            hold_change = (action * self.cash) // reference_price
            cash_change = -hold_change * reference_price
        else:
            hold_change = -floor(abs(action) * self.hold)
            cash_change = -hold_change * reference_price
        diff = (reference_price / self.avg_price - 1) * hold_change if self.avg_price > 0 else 0
        if hold_change > 0:
            self.avg_price = (self.avg_price * self.hold + hold_change * reference_price) / (self.hold + hold_change)
        self.cash += cash_change
        self.hold += hold_change
        self.estimated = self.hold * reference_price + self.cash
        # net value based reward log %
        return 0 if hold_change >= 0 else diff, hold_change

    def describe(self):
        print("= Position Summary =================================")
        print("Current balance:", self.cash)
        print("Holding stock:", self.hold)
        print("Last stock price (close):", self.price_cache[-1])
        print("Estimated balance:", self.estimated)
        print("----------------------------------------------------")

    def show_env(self):
        print("= Environment Setting ==============================")
        print("Ticker:", self.ticker)
        print("From:", self.interval[0])
        print("To:", self.interval[1])
        print("----------------------------------------------------")

    def close(self):
        self.db.close()


class StockTickEmulator(StockEmulator):
    # constant
    PRICE_CACHE_SIZE = 120
    STATE_SIZE = 13
    ACTION_SIZE = 3
    TABLE_NAME = "STOCK_TICK_PRICES"
    LOG_STRUCTURE = [
        "Date",
        "Price",
        "Bollinger_lower",
        "Bollinger_upper",
        "Moving_avg_20",
        "Moving_avg_60",
        "Moving_avg_120",
        "RSI_14",
        "Size",
        "Position_value",
        "Avg_bought_price",
        "Action"
    ]

    @classmethod
    def get_state_dict(cls, data=None) -> dict:
        if data is None:
            return {x: [] for x in cls.LOG_STRUCTURE}
        tmp = {}
        for i in range(len(cls.LOG_STRUCTURE)):
            tmp[cls.LOG_STRUCTURE[i]] = data[i]
        return tmp

    def __init__(self, cash=10000, batch_size=10000, limit_train_domain=300, interval_length=300, ticker_exclusion=None,
                 timestep_skip=0):
        super().__init__(cash, batch_size, limit_train_domain, interval_length, ticker_exclusion)
        self.db = CSVInteractor(CSVInteractor.DEFAULT_CFG)
        self.db.connect()

    def step(self, action) -> tuple[list, int, bool, dict]:
        """
        Returns next state. Values are normalized.
        :param action:
        :param interval:
        :return: quadruple of (state, reward, end, raw)
        state : [open, close, high, low, bollinger_lower, bollinger_upper,
            moving_avg_20, moving_avg_60, moving_avg_120, 1 / volume, position_value, avg_bought_price]
        reward : Reward based on estimated value change rate
        end : True if interval finished
        raw : Data before normalize.
        """
        row, end = self.next_row()
        price, volume = float(row[-2]), int(row[-3])
        self.price_cache.append(price)
        price_cache_list = list(self.price_cache)
        reward, hold_change = self.update_state(price, action)
        local_max, local_min = max(price_cache_list[-100:]), min(price_cache_list[-100:])
        normalized_price = [((price - local_min) / (local_max - local_min)) if local_max != local_min else 0.5]
        avg_index = (
                get_moving_avg(price_cache_list, stddev_factor=[-2, 2, 0])
                + get_moving_avg(price_cache_list, alpha=0.1, length=60)
                + get_moving_avg(price_cache_list, alpha=0.1, length=120)
        )
        state = (
                normalized_price
                + [x / (price * 2) for x in avg_index]
                + [get_rsi(price_cache_list, length=14), 1 / (1 + log1p(volume))]
                + [self.estimated / (self.seed_money * 2), self.avg_price / (price * 2)]
        )
        raw_data = StockTickEmulator.get_state_dict(
            [row[0], price]
            + avg_index
            + [get_rsi(price_cache_list, 14), volume]
            + [self.estimated, self.avg_price, hold_change]
        )
        self.state_pool.append(state)
        return list(self.state_pool), reward, end, raw_data

if __name__ == "__main__":
    f = -1
    env = StockEmulator(interval_length=1000, ticker_exclusion=[])
    for i in range(1000):
        state = env.reset(pooling=10)
        while True:
            f *= -1
            state, reward, done, log = env.step(random.uniform(-1, 1))
            print(log['Action'], done)
            if done:
                break
