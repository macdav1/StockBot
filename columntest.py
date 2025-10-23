import xgboost as xgb
model = xgb.XGBClassifier()
model.load_model("trained_model.xgb")
print(model.n_features_in_)  # should print 4
