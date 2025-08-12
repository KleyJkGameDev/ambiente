import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)

ds = pd.read_csv("/home/kleytinn/Desktop/Python_Learn/analisys/online_shoppers_intention.csv")

#ds.head() printar dataset
ds.info() #informações gerais sobre o dataset

val_unic = []
for i in ds.columns.tolist():
    print(f"{i}: {len(ds[i].astype(str).value_counts())}")
    val_unic.append(len(ds[i].astype(str).value_counts()))

#sns.boxplot(data= ds, y= "PageValues")
#plt.show()
#sns.histplot(data= ds, x= "PageValues")
#plt.show()
#sns.countplot(data= ds, x= "PageValues")
#plt.show()