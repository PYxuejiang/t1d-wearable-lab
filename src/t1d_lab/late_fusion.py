"""Modality experts, causal out-of-fit stacking and low-run balanced training."""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CLOCK=['hour_sin','hour_cos'];MASK=['wrist_present','ecg_present']
MODALITIES=['ecg','ppg','eda']
COLUMNS={
    'ecg':['ecghr','ecghrv','ecgrrstd','ecghr_dev']+CLOCK,
    'ppg':['hr','hrv','rrstd','ppgq','motion','hr_dev','hr_residual']+CLOCK,
    'eda':['eda','edav','temp','eda_dev','temp_dev','motion']+CLOCK,
    'mask_clock':MASK+CLOCK,
}
COLUMNS['early']=list(dict.fromkeys(sum([COLUMNS[k] for k in MODALITIES],[])+MASK))


def available(frame,arm):
    wrist=frame.wrist_present.eq(1).to_numpy();ecg=frame.ecg_present.eq(1).to_numpy()
    return ecg if arm=='ecg' else wrist if arm in ('ppg','eda') else wrist|ecg


def training_weights(frame,mode):
    """Run IDs use all reference rows before availability filtering, provided by caller."""
    if mode not in ('point','run'):raise ValueError(mode)
    w=pd.Series(0.,index=frame.index)
    for _,person in frame.groupby('subject'):
        for label,g in person.groupby('label_low'):
            if mode=='point':v=np.ones(len(g))
            else:
                key='low_run' if label else 'negative_block'
                counts=g[key].value_counts();v=1/g[key].map(counts).to_numpy(float)
            w.loc[g.index]=v/v.sum()/person.label_low.nunique()
    values=w.to_numpy();return values/values.mean() if len(values) else values


def add_weight_groups(frame):
    g=frame.copy();t=pd.DatetimeIndex(g.decision_time).as_unit('ns').asi8;y=g.label_low.to_numpy(bool)
    g['low_run']=np.cumsum(np.r_[True,(y[1:]!=y[:-1])|(np.diff(t)>450e9)])
    g['negative_block']=t//int(6*3600e9)
    return g


def fit_model(x,y,w,name,seed):
    prior=float(np.average(y,weights=w)) if len(y) else 0.
    if len(y)<100 or np.sum(y)<5 or len(np.unique(y))<2:return None,prior
    if name=='logistic_C0.1':m=LogisticRegression(C=.1,max_iter=1500,random_state=seed)
    elif name=='hgb_leaves7':m=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=7,min_samples_leaf=40,learning_rate=.04,l2_regularization=30,early_stopping=False,random_state=seed)
    elif name=='extra_trees_depth5':m=ExtraTreesClassifier(n_estimators=160,max_depth=5,min_samples_leaf=10,max_features=.8,n_jobs=2,random_state=seed)
    else:raise ValueError(name)
    pipeline=make_pipeline(SimpleImputer(strategy='constant',fill_value=0,keep_empty_features=True),StandardScaler(),m)
    pipeline.fit(x,y,**{list(pipeline.named_steps)[-1]+'__sample_weight':w})
    return pipeline,prior


def predict(model,prior,x):
    if len(x)==0:return np.array([])
    return model.predict_proba(x)[:,1] if model is not None else np.full(len(x),prior)


def stack_design(frame,modality_scores):
    p=np.column_stack([modality_scores[k] for k in MODALITIES]);valid=np.isfinite(p)
    clipped=np.clip(p,1e-4,1-1e-4)
    logits=np.where(valid,np.log(clipped/(1-clipped)),0)
    return np.column_stack([logits,valid.astype(float),frame[CLOCK].to_numpy()])


def mean_fusion(modality_scores):
    p=np.column_stack([modality_scores[k] for k in MODALITIES]);counts=np.isfinite(p).sum(axis=1)
    return np.divide(np.nansum(p,axis=1),counts,out=np.full(len(p),np.nan),where=counts>0)
