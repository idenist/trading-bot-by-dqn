from datetime import datetime, date

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import random
from tqdm import tqdm

from collections import deque

from emulator import StockEmulator
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf


def plot_trading_log(log_df):
    if not isinstance(log_df.index, pd.DatetimeIndex):
        log_df = log_df.copy()  # Avoid modifying the original DataFrame
        log_df['Date'] = pd.to_datetime(log_df['Date'])
        log_df.set_index('Date', inplace=True)

    # Define additional plots for Bollinger Bands, Moving Averages, and Trading Actions
    add_plots = [
        mpf.make_addplot(log_df['Bollinger_lower'], color='yellow', linestyle='dashed'),
        mpf.make_addplot(log_df['Bollinger_upper'], color='yellow', linestyle='dashed'),
        mpf.make_addplot(log_df['Moving_avg_20'], color='red', linestyle='solid'),
        mpf.make_addplot(log_df['Moving_avg_60'], color='orange', linestyle='solid'),
        mpf.make_addplot(log_df['Moving_avg_120'], color='pink', linestyle='solid'),
        mpf.make_addplot(log_df['Action'], type='bar', panel=2, color='cyan', alpha=0.7, ylabel='Actions')
    ]

    # Plot candlestick chart with volume and additional indicators
    mpf.plot(
        log_df, type='candle', volume=True, style='charles',
        addplot=add_plots, ylabel='Stock Price', title='Stock Price and Trading Actions',
        figsize=(12, 8)
    )


# Hyperparameters
GAMMA = 0.99
LEARNING_RATE = 0.001
BATCH_SIZE = 64
MEMORY_SIZE = 10000
EPSILON_START = 1.0
EPSILON_DECAY = 0.998
EPSILON_MIN = 0.01
TARGET_UPDATE = 10


# Neural Network for approximating Q-values
class QNetwork(nn.Module):
    def __init__(self, state_size, action_size):
        super(QNetwork, self).__init__()
        self.fc1 = nn.Linear(state_size, 128)
        self.fc2 = nn.Linear(128, 128)
        self.fc3 = nn.Linear(128, action_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        x = torch.tanh(x)
        return x

class CNNQNetwork(nn.Module):
    def __init__(self, stack_size, action_size):
        super(CNNQNetwork, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=stack_size, out_channels=16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(in_channels=16, out_channels=32, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.fc = nn.Linear(32, action_size)

    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        x = x.mean(dim=-1)  # Global average pooling
        x = self.fc(x)
        return x


# Replay memory for experience replay
class ReplayMemory:
    def __init__(self, capacity):
        self.memory = deque(maxlen=capacity)

    def push(self, transition):
        self.memory.append(transition)

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


# Epsilon-greedy action selection
def select_action(state, policy_net, epsilon):
    if random.random() < epsilon:
        return random.randint(0, 2)
    with torch.no_grad():
        return policy_net(torch.from_numpy(np.array(state)).float().unsqueeze(0)).max(1)[1].item()



# Optimize the policy network
def optimize_model(memory, optimizer, policy_net, target_net, criterion):
    if len(memory) < BATCH_SIZE:
        return

    transitions = memory.sample(BATCH_SIZE)
    state, action, next_state, reward, done = zip(*transitions)
    state = torch.tensor(state, dtype=torch.float32)
    action = torch.tensor(action, dtype=torch.long).unsqueeze(1)
    next_state = torch.tensor(next_state, dtype=torch.float32)
    reward = torch.tensor(reward, dtype=torch.float32).unsqueeze(1)
    done = torch.tensor(done, dtype=torch.float32).unsqueeze(1)

    q_values = policy_net(state).gather(1, action)
    next_q_values = target_net(next_state).max(1)[0].detach().unsqueeze(1)
    target = reward + (GAMMA * next_q_values * (1 - done))

    loss = criterion(q_values, target)

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()


# Main DQN loop
def main_DQN_loop(
        LEARNING_RATE=0.001,
        MEMORY_SIZE=10000,
        EPSILON_START=1.0,
        EPSILON_DECAY=0.99,
        EPSILON_MIN=0.01,
        TARGET_UPDATE=10,
        stack_size=1,
        train_episode=100,
        interval_length=600,
        test_ticker=None,
        save_path='dqn_aapl.pth'
):
    env = StockEmulator(interval_length=interval_length, ticker_exclusion=test_ticker, limit_train_domain=300)
    state_size = env.STATE_SIZE
    action_size = env.ACTION_SIZE
    if stack_size <= 1:
        policy_net = QNetwork(state_size, action_size)
        target_net = QNetwork(state_size, action_size)
        target_net.load_state_dict(policy_net.state_dict())
        target_net.eval()
    else:
        policy_net = CNNQNetwork(stack_size, action_size)
        target_net = CNNQNetwork(stack_size, action_size)
        target_net.load_state_dict(policy_net.state_dict())
        target_net.eval()

    memory = ReplayMemory(MEMORY_SIZE)
    optimizer = optim.Adam(policy_net.parameters(), lr=LEARNING_RATE)
    criterion = nn.MSELoss()

    epsilon = EPSILON_START
    pbar = tqdm(range(train_episode))
    for episode in pbar:
        cnt = 0
        state = env.reset(pooling=stack_size)
        while True:
            action = select_action(state, policy_net, epsilon)
            next_state, reward, done, raw = env.step(action - 1)
            memory.push((state, action, next_state, reward, done))
            if cnt % 50 == 0:
                pbar.set_postfix(
                    action=f'{"BUY " if raw["Action"] > 0 else ("SELL" if raw["Action"] < 0 else "HOLD")} {abs(int(raw["Action"])) if raw["Action"] != 0 else ""} {env.ticker} stock(s) for {raw["Close"]}',
                    epsilon=f"{epsilon:.3f}",
                    reward=f"{reward:+.3f}",
                )
            cnt += 1
            state = next_state
            optimize_model(memory, optimizer, policy_net, target_net, criterion)

            if done:
                break
        # Decay epsilon
        epsilon = max(EPSILON_MIN, epsilon * EPSILON_DECAY)

        # Update target network
        if episode % TARGET_UPDATE == 0:
            target_net.load_state_dict(policy_net.state_dict())
    env.close()
    torch.save(policy_net.state_dict(), save_path)


def test_DQN(
        weight_path="dqn_aapl.pth",
        stack_size=1,
        interval_length=600,
        test_ticker='AAPL',
        test_range:tuple[int, int]=None
):
    env = StockEmulator(interval_length=interval_length, limit_train_domain=0, ticker_exclusion=test_ticker, )
    state_size = env.STATE_SIZE
    action_size = env.ACTION_SIZE
    if stack_size <= 1:
        trained_policy_net = QNetwork(state_size, action_size)
        trained_policy_net.load_state_dict(torch.load(weight_path))
    else:
        trained_policy_net = CNNQNetwork(stack_size, action_size)
        trained_policy_net.load_state_dict(torch.load(weight_path))
    state = env.reset(ticker=test_ticker, interval=test_range, pooling=stack_size)
    log = StockEmulator.get_state_dict()
    while True:
        action = select_action(state, trained_policy_net, EPSILON_MIN)
        # action = 1 if action > 0.3 else (-1 if action < -0.3 else 0)
        next_state, reward, done, raw = env.step(action - 1)
        if raw["Action"] != 0:
            print(f'{"BUY " if raw["Action"] > 0 else ("SELL" if raw["Action"] < 0 else "HOLD")} {abs(int(raw["Action"])) if raw["Action"] != 0 else "":4} stock(s) for {raw["Close"]}',
)
        for k, v in raw.items():
            log[k].append(v)
        state = next_state
        if done:
            break

    env.show_env()
    env.describe()
    log_df = pd.DataFrame(log)
    plot_trading_log(log_df)


if __name__ == "__main__":
    path = "DQN_aapl.pth"
    # main_DQN_loop(
    #     EPSILON_DECAY=0.9,
    #     save_path=path, test_ticker='AAPL', interval_length=100, stack_size=30, train_episode=1000)
    test_DQN(
        weight_path=path, stack_size=30,
        interval_length=100,
        test_ticker='AAPL',
        test_range=(0, 100)
    )