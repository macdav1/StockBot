#!/bin/bash
cd ~/Stock_app
source env_predictor/bin/activate
python backtest_runner.py
deactivate

