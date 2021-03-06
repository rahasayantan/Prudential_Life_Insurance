# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 08:24:36 2016

@author: bishwarup
"""

import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

import theano
from keras.models import Sequential
from keras.layers.core import Dense, Dropout, Activation
from keras.layers.normalization import BatchNormalization
from keras.layers.advanced_activations import PReLU
from keras.utils import np_utils
from keras.layers.advanced_activations import PReLU
from keras.optimizers import SGD, Adadelta, Adagrad
from keras.optimizers import Adagrad,SGD,Adadelta
from keras.regularizers import l1, l2, l1l2
from keras.callbacks import Callback

os.chdir("/home/bishwarup/Kaggle/Prudential")
np.random.seed(133)
nb_epoch = 15
batch_size = 28
n_class = 1

def load_data():

    print "\nLoading..."
    train = pd.read_csv("Data/train.csv")
    test = pd.read_csv("Data/test.csv")
    
    print "\nProcessing..."
    train["train_flag"] = 1
    test["train_flag"] = 0
    test["Response"] = -1
    
    alldata = train.append(test, ignore_index = True)
    
    exclude_cols = ["Id", "Response", "train_flag", "Product_Info_2"]
    selected_cols = [x for x in train.columns if x not in exclude_cols]
    
    alldata["na_count"] = alldata[selected_cols].apply(lambda x: x.isnull().sum(), axis = 1)
    alldata["zero_count"] = alldata[selected_cols].apply(lambda x: x.value_counts().get(0, 0), axis = 1)
    alldata["fi_1"] = alldata["Medical_History_23"] * alldata["Medical_History_15"]
    alldata["fi_2"] = alldata["Medical_History_23"] * alldata["Medical_History_4"]
    alldata["fi_3"] = alldata["Medical_History_23"] * alldata["Medical_History_39"]
    alldata["fi_4"] = alldata["Medical_History_15"] * alldata["Medical_History_39"]
    alldata["fi_5"] = alldata["Medical_History_4"]  * alldata["Medical_History_39"]
    alldata["fi_6"] = alldata["Medical_History_23"] * alldata["Medical_History_6"]
    alldata["fi_7"] = alldata["Medical_History_6"] - alldata["Medical_History_16"]
    alldata["fi_8"] = alldata["Medical_History_6"] + alldata["Medical_History_13"]
    alldata["fi_9"] = alldata["Medical_History_32"] + alldata["Medical_History_40"]
    alldata["fi_10"] = alldata["Medical_Keyword_15"] + alldata["Medical_Keyword_3"]
    alldata["fi_11"] = alldata["Medical_Keyword_15"] + alldata["Medical_Keyword_48"]
    alldata["fi_12"] = alldata["Medical_Keyword_3"] + alldata["Medical_Keyword_48"]
    alldata["fi_13"] = alldata["InsuredInfo_6"] - alldata["Insurance_History_2"]
    alldata["fi_14"] = alldata["BMI"] / alldata["Medical_History_23"]
    alldata["fi_15"] = alldata["BMI"]/ (alldata["Medical_History_15"] + 1)
    alldata["fi_16"] = alldata["BMI"] + alldata["Ins_Age"]
    alldata["fi_17"] = alldata["Ins_Age"] - alldata["Product_Info_4"]
    alldata["fi_18"] = alldata["Ins_Age"] / alldata["InsuredInfo_6"]
    alldata["fi_19"] = alldata["Ins_Age"] - alldata["Medical_History_23"]
    
    dummy_df = pd.get_dummies(alldata["Product_Info_2"], prefix_sep = "_")
    dummy_df[dummy_df == 0] = -1
    alldata.drop("Product_Info_2", axis = 1, inplace = True)
    
    # impute NaNs with medians    
    for x in alldata.columns:
        if pd.isnull(alldata[x]).sum() > 0:
            alldata[x].fillna(alldata[x].median(), inplace = True)
    
    normalize_cols = [f for f in alldata.columns if f not in ["Id", "Response", "train_flag"]]
    norm_df = alldata[normalize_cols]
    scalar = StandardScaler()
    normalized_df = pd.DataFrame(scalar.fit_transform(norm_df))
    normalized_df.columns = normalize_cols
    alldata.drop(normalize_cols, axis = 1, inplace = True)    
    
    alldata = pd.concat([alldata, dummy_df], axis = 1)
    alldata = pd.concat([alldata, normalized_df], axis = 1)
    
    ptr = alldata[alldata["train_flag"] == 1]
    pte = alldata[alldata["train_flag"] == 0]
    
    return ptr, pte
    

def build_model2(train):

    input_dim = train.shape[1]
    classes = 1    
    
    model = Sequential()
    model.add(Dense(256, input_dim= input_dim, W_regularizer=l1(1e-5))) 
    model.add(Dropout(0.1))
    model.add(PReLU())
    model.add(Dropout(0.5))
    
    model.add(Dense(128))
    model.add(PReLU())
    model.add(Dropout(0.5))
    
    model.add(Dense(25))
    model.add(PReLU())
    model.add(Dropout(0.5))
    
    model.add(Dense(classes))
    model.add(Activation("linear"))
        
    model.compile(loss='mse', optimizer="adam")
    return model    

def fit_model(ptr, pte):
    
    feature_names = [f for f in ptr.columns if f not in ["Id", "Response", "train_flag"]]

    print "\nStarting validation...."
    fold_ids = pd.read_csv("ensemble2/validation_id.csv")

    eval_matrix = pd.DataFrame(columns = ["Fold", "Id", "ground_truth", "nn4_preds"])        
    test_matrix = pd.DataFrame({"Id" : pte["Id"]})
    
    for i in xrange(10):
        
        val_ids = fold_ids.ix[:, i].dropna()
        idx = ptr["Id"].isin(list(val_ids))
        
        trainingSet = ptr[~idx]
        validationSet = ptr[idx]
        
        tr_Y = np.array(trainingSet["Response"].copy())
        val_Y = np.array(validationSet["Response"].copy())
        
        tr_X = np.matrix(trainingSet[feature_names])
        val_X = np.matrix(validationSet[feature_names])
              
        model = build_model2(tr_X)
        model.fit(tr_X, tr_Y, nb_epoch=nb_epoch, batch_size=batch_size, validation_data= (val_X, val_Y))
        
        preds = model.predict(val_X, batch_size=128).ravel()
        df = pd.DataFrame({"Fold" : np.repeat((i + 1), validationSet.shape[0]) ,"Id" : validationSet["Id"], "ground_truth" : validationSet["Response"], 
                            "nn4_preds" : preds})
        eval_matrix = eval_matrix.append(df, ignore_index = True)
    
    
    tr_X = np.matrix(ptr[feature_names])
    tr_Y = np.array(ptr["Response"]).copy()    
    te_X = np.matrix(pte[feature_names])  

    model = build_model2(tr_X)
    model.fit(tr_X, tr_Y, nb_epoch = nb_epoch, batch_size = batch_size)
    
    tpreds = model.predict(te_X, batch_size=128).ravel()
    test_matrix["nn4_preds"] = tpreds
    return eval_matrix, test_matrix

#############################

ptr, pte = load_data()
validm, testm = fit_model(ptr, pte)

validm.to_csv("ensemble2/nn4_eval.csv", index = False)
testm.to_csv("ensemble2/nn4_test.csv", index = False)
