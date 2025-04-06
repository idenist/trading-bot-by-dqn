import datetime
import time
import gc
from typing import Any, Generator, Optional, Tuple

import pandas as pd

import psycopg2
from psycopg2.extras import DictCursor


class DBInteractor:
    DEFAULT_CFG = {
        "dbname": "stock_data",
        "user": "mj008",
        "password": "mj102203",
        "host": "localhost",
        "port": 5432
    }
    def __init__(self, cfg: dict):
        self.conn = None
        self.cursor = None
        self.lock = False
        self.cfg = cfg
        self.is_connected = False

    def connect(self):
        """데이터베이스 연결 생성"""
        if self.is_connected:
            return
        self.conn = psycopg2.connect(**self.cfg)
        self.cursor = self.conn.cursor(cursor_factory=DictCursor)
        self.is_connected = True

    def close(self):
        """데이터베이스 연결 종료"""
        if not self.is_connected:
            return
        self.cursor.close()
        self.conn.close()
        self.is_connected = False
        self.lock = False

    def unlock(self):
        self.lock = False

    def get_data_amount(self, table_name, ticker):
        query = f"""
        SELECT COUNT(*) AS amount FROM {table_name} WHERE ticker = %s;
        """
        self.cursor.execute(query, (ticker,))
        return self.cursor.fetchone()["amount"]


    def fetch_data_batch(self, table_name, ticker, offset, limit):
        # Validate inner state.
        assert self.is_connected, "DB not connected."
        assert not self.lock, "Resource is locked."
        # Count rows.
        query = f"""
        SELECT count(*) as amount
        FROM (SELECT * 
        FROM {table_name}
        WHERE ticker = %s AND volume <> 0
        OFFSET %s LIMIT %s) AS T;
        """
        self.cursor.execute(query, (ticker, offset, limit))
        cnt = int(self.cursor.fetchone()["amount"])
        # Fetch rows.
        query = f"""
        SELECT *
        FROM {table_name}
        WHERE ticker = %s AND volume <> 0
        OFFSET %s LIMIT %s;
        """
        self.cursor.execute(query, (ticker, offset, limit))
        self.lock = True
        return cnt

    def get_next_batch(self, batch_size):
        assert self.lock, "Fetch has not executed"
        if batch := self.cursor.fetchmany(batch_size):
            return batch
        else:
            self.lock = False

    def fetch_tickers(self, table_name):
        query = f"SELECT DISTINCT TICKER FROM {table_name};"
        self.cursor.execute(query)
        return [x[0] for x in self.cursor.fetchall()]

    def __load_csv_tick_data(self, csv_path):
        def process_ns(row):
            return int(row['TIME_M'].split('.')[-1][6:])
        def cast(r):
            return (
                r[0], r[1], r[2], r[3],
                float(r[4]), r[5],
                int(r[6]), float(r[7]),
                int(r[8]), float(r[9])
            )
        chunksize = 10 ** 5
        cnt = 0
        query = """
        INSERT INTO stock_tick_prices (date, time_m, ex, sym_root, sym_suffix, tr_scond, size, price, tr_corr, time_n)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date, time_m, time_n) DO NOTHING;
        """
        with open(r'C:\Users\mj008\Documents\GradProj\ProjectData\ishpfyjzygars3it.csv', "rb") as f:
            num_lines = sum(1 for _ in f)
        print(f"Total lines: {num_lines}")
        with pd.read_csv(csv_path, chunksize=chunksize) as csv:
            for chunk in csv:
                print(progress := f"\r{cnt:8} / {num_lines // chunksize + 1:8}", end='')
                chunk['TIME_N'] = chunk.apply(process_ns, axis=1)
                print(progress, "TIME_N conversion", end='')
                records = chunk.to_records(index=False)
                print(progress, "Type conversion", end='')
                self.cursor.executemany(query, map(cast, records))
                print(progress, "Transaction complete. Committing.", end='')
                self.conn.commit()
                del [[chunk, records]]
                gc.collect()
                cnt += 1

    def insert_data(self, table_name, data):
        assert self.is_connected, "DB not connected."
        assert not self.lock, "Resource is locked."
        query = f'''INSERT INTO {table_name}
        (TRADE_DATE, TICKER, OPEN, CLOSE, HIGH, LOW, VOLUME)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        on conflict do nothing;'''
        self.cursor.executemany(query, data)



class CSVInteractor:
    DEFAULT_CFG = {
        "file": r'C:\Users\mj008\Documents\GradProj\ProjectData\ishpfyjzygars3it.csv',
        "mode": "r",
        "encoding": "utf-8"
    }
    def __init__(self, cfg: dict):
        self.limit = -1
        self.info = dict()
        self.file = None
        self.lock = False
        self.cursor = 0
        self.cfg = cfg
        self.is_connected = False
        self.cache = list()
        self.current_index = 0


    def connect(self):
        if self.is_connected:
            return
        self.file = open(**self.cfg)
        self.is_connected = True
        self.analyze()

    def close(self):
        """데이터베이스 연결 종료"""
        if not self.is_connected:
            return
        self.file.close()
        self.is_connected = False
        self.lock = False

    def unlock(self):
        self.lock = False

    def analyze(self):
        self.file.seek(1)
        for line in self.file:
            ticker = line.split(',')[3]
            if ticker == 'SYM_ROOT':
                continue
            if ticker not in self.info:
                self.info[ticker] = {"length": 1}
            else:
                self.info[ticker]["length"] += 1

    def get_data_amount(self, table_name, ticker):
        return self.info[ticker]['length']

    def fetch_data_batch(self, table_name, ticker, offset, limit):
        # Validate inner state.
        assert self.is_connected, "DB not connected."
        assert not self.lock, "Resource is locked."
        assert offset + limit <= self.get_data_amount(table_name, ticker), f"Given limit is too big.\nOffset+Limit={offset + limit}\nTotal rows: {self.info[ticker]['length']}"
        # Fetch rows.
        self.cache.clear()
        self.file.seek(1)
        i = 0
        for row in self.file:
            if len(self.cache) >= limit:
                break
            if row.split(',')[3] == ticker:
                if i >= offset:
                    date, time = row.split(',')[:2]
                    time_n = int(str(time)[-3:])
                    time_m = datetime.time.fromisoformat(str(time)[:-3].zfill(15))
                    volume, price = row.split(',')[-3:-1]
                    self.cache.append(tuple([date, time_m, time_n] + list(row[2:-3]) + [int(volume), float(price), row[-1]]))
            i += 1
        self.current_index = 0
        self.lock = True
        return len(self.cache)

    def get_next_batch(self, batch_size):
        assert self.lock, "Fetch has not executed"
        try:
            return self.cache[self.current_index : min(self.current_index + batch_size, len(self.cache))]
        finally:
            self.current_index += batch_size
            if self.current_index >= len(self.cache):
                self.lock = False
                self.cache.clear()

    def fetch_tickers(self, table_name):
        return [k for k in self.info.keys()]


if __name__ == "__main__":
    s = time.time()
    csv = CSVInteractor(cfg=CSVInteractor.DEFAULT_CFG)
    csv.connect()
    print(time.time() - s)
    s = time.time()
    csv.fetch_data_batch('', 'AAPL', 1000000, 100000)
    print(time.time() - s)
    s = time.time()
    for i in csv.get_next_batch(10000):
        print(len(i))
    print(time.time() - s)
    print(csv.fetch_tickers(''))
