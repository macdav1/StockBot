#!/bin/bash

# Activate the predictor environment
source /home/dave/Stock_app/env_predictor/bin/activate

# Launch Streamlit dashboard on port 8502
streamlit run /home/dave/Stock_app/dashboard.py --server.port 8502

# Deactivate after streamlit exits
deactivate


