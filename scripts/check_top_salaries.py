import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import sqlite3

df = pd.read_csv('data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv')

print("--- TOP 35 SALARIES ON ENTIRE SLATE (ALL POSITIONS) ---")
print(df[['Nickname', 'Position', 'Team', 'Opponent', 'Salary', 'FPPG', 'Injury Indicator']].sort_values(by='Salary', ascending=False).head(35).to_string())

print("\n--- SALARY BREAKDOWN BY POSITION ---")
print(df.groupby('Position')['Salary'].agg(['count', 'min', 'max', 'median', 'mean']).to_string())
