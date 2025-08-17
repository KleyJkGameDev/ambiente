# -*- coding: utf-8 -*-
"""
Pipeline completo com:
- Export do SQLite (JOIN: sales_saleitem + sales_sale + products_product + products_category + products_brand)
- Engenharia de features: revenue, agregações diária/semanal
- Flags de sazonalidade (BR): Volta às Aulas, Carnaval, Semana Santa, São João,
  Dia dos Namorados, Dia das Mães, Dia dos Pais, Dia das Crianças, Black Friday, Natal
- ONE-HOT semanal (TOP-K) para marcas e categorias
- Split temporal (treino = mais antigo; teste = mais recente)
- Treino de modelo (XGBoost se disponível; fallback: GradientBoosting)
- Métricas + figuras (correlação, importâncias, real vs previsto)
Saídas em ./outputs
"""

import os
import re
import sqlite3
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, timedelta

# XGBoost opcional; se não houver, usa GradientBoosting como fallback
try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except Exception:
    HAS_XGB = False

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error

# ----------------------------- CONFIG -----------------------------
DB_PATH = r"./db-copy.sqlite3"          # <<< AJUSTE AQUI se necessário
OUT_DIR = r"./outputs"             # <<< AJUSTE AQUI se quiser outra pasta
os.makedirs(OUT_DIR, exist_ok=True)

CSV_JOINED = os.path.join(OUT_DIR, "sales_saleitem_joined_from_db.csv")
CSV_LINE   = os.path.join(OUT_DIR, "sales_saleitem_with_revenue.csv")
CSV_DAILY  = os.path.join(OUT_DIR, "daily_sales.csv")
CSV_WEEKLY = os.path.join(OUT_DIR, "weekly_sales.csv")

PNG_CORR   = os.path.join(OUT_DIR, "correlacao_heatmap.png")
PNG_FIMP   = os.path.join(OUT_DIR, "feature_importances.png")
PNG_AVP    = os.path.join(OUT_DIR, "actual_vs_pred.png")

TOP_K = 5  # top-N marcas e categorias para one-hot semanal

# ----------------------- UTIL: datas móveis BR ---------------------
def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    month = (h + l - 7*m + 114) // 31
    day = ((h + l - 7*m + 114) % 31) + 1
    return date(year, month, day)

def carnaval_tuesday(year: int) -> date:
    return easter_sunday(year) - timedelta(days=47)

def semana_santa_range(year: int):
    pascoa = easter_sunday(year)
    start = pascoa - timedelta(days=7)
    end = pascoa
    return start, end

def black_friday_date(year: int) -> date:
    d = date(year, 11, 1)
    offset = (3 - d.weekday()) % 7  # quinta = 3
    first_thu = d + timedelta(days=offset)
    fourth_thu = first_thu + timedelta(weeks=3)
    return fourth_thu + timedelta(days=1)

def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    first = d + timedelta(days=offset)
    return first + timedelta(weeks=n-1)

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"(^_+|_+$)", "", s)
    return (s or "unknown")[:40]

# -------------------------- 1) EXPORTAÇÃO --------------------------
def exportar_joinado(db_path: str, out_csv: str) -> pd.DataFrame:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco não encontrado: {db_path}")

    conn = sqlite3.connect(db_path)
    sql = """
    SELECT
        ssi.id,
        ssi.quantity,
        ssi.price_at_sale,
        ssi.created_at,
        ssi.updated_at,
        ssi.brand_id,
        ssi.product_id,
        ssi.sale_id,
        ssi.category_id,
        pp.title AS product_name,
        pc.name  AS category_name,
        pb.name  AS brand_name,
        ss.created_at AS sale_date
    FROM sales_saleitem ssi
    JOIN products_product  pp ON ssi.product_id = pp.id
    JOIN products_category pc ON ssi.category_id = pc.id
    JOIN products_brand    pb ON ssi.brand_id   = pb.id
    JOIN sales_sale        ss ON ssi.sale_id    = ss.id
    ORDER BY ss.created_at ASC, ssi.id ASC;
    """
    df = pd.read_sql_query(sql, conn)
    conn.close()

    df.to_csv(out_csv, index=False)
    return df

# --------------- 2) FEATURE ENGINEERING + EDA ----------------------
def add_seasonality_flags_daily(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year

    flags = [
        "volta_as_aulas","carnaval","semana_santa","sao_joao",
        "dia_namorados","dia_maes","dia_pais","dia_criancas",
        "black_friday","natal"
    ]
    for f in flags:
        d[f] = 0

    for y in sorted(d["year"].unique()):
        va_start, va_end = date(y, 1, 20), date(y, 3, 10)
        carn_tue = carnaval_tuesday(y); carn_fri = carn_tue - timedelta(days=4); carn_end = carn_tue
        ss_ini, ss_fim = semana_santa_range(y)
        sj_ini, sj_fim = date(y, 6, 10), date(y, 6, 30)
        dn_ini, dn_fim = date(y, 6, 5), date(y, 6, 12)
        dmae = nth_weekday_of_month(y, 5, weekday=6, n=2); dmae_ini = dmae - timedelta(days=dmae.weekday()); dmae_fim = dmae
        dpai = nth_weekday_of_month(y, 8, weekday=6, n=2); dpai_ini = dpai - timedelta(days=dpai.weekday()); dpai_fim = dpai
        dc_ini, dc_fim = date(y, 10, 5), date(y, 10, 12)
        bf = black_friday_date(y); bf_ini = bf - timedelta(days=bf.weekday()); bf_fim = bf_ini + timedelta(days=6)
        nat_ini, nat_fim = date(y, 12, 10), date(y, 12, 25)

        mask_y = d["year"] == y
        dd = d.loc[mask_y, "date"].dt.date
        d.loc[mask_y & dd.between(va_start, va_end), "volta_as_aulas"] = 1
        d.loc[mask_y & dd.between(carn_fri, carn_end), "carnaval"] = 1
        d.loc[mask_y & dd.between(ss_ini, ss_fim), "semana_santa"] = 1
        d.loc[mask_y & dd.between(sj_ini, sj_fim), "sao_joao"] = 1
        d.loc[mask_y & dd.between(dn_ini, dn_fim), "dia_namorados"] = 1
        d.loc[mask_y & dd.between(dmae_ini, dmae_fim), "dia_maes"] = 1
        d.loc[mask_y & dd.between(dpai_ini, dpai_fim), "dia_pais"] = 1
        d.loc[mask_y & dd.between(dc_ini, dc_fim), "dia_criancas"] = 1
        d.loc[mask_y & dd.between(bf_ini, bf_fim), "black_friday"] = 1
        d.loc[mask_y & dd.between(nat_ini, nat_fim), "natal"] = 1

    return d

def preparar_dados(df_joined: pd.DataFrame):
    df = df_joined.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df["revenue"]   = df["quantity"] * df["price_at_sale"]

    # Agregado diário
    daily = (
        df.groupby(df["sale_date"].dt.date)
          .agg(total_revenue=("revenue", "sum"),
               total_qty=("quantity", "sum"),
               num_items=("id", "count"))
          .reset_index()
          .rename(columns={"sale_date": "date", "index": "date"})
    )
    daily["date"] = pd.to_datetime(daily["date"])

    # Flags sazonais no diário
    daily = add_seasonality_flags_daily(daily)

    # Agregado semanal (labels = segunda-feira)
    weekly = (
        daily.set_index("date")
             .resample("W-MON")
             .agg(
                 total_revenue=("total_revenue", "sum"),
                 total_qty=("total_qty", "sum"),
                 num_items=("num_items", "sum"),
                 volta_as_aulas=("volta_as_aulas", "max"),
                 carnaval=("carnaval", "max"),
                 semana_santa=("semana_santa", "max"),
                 sao_joao=("sao_joao", "max"),
                 dia_namorados=("dia_namorados", "max"),
                 dia_maes=("dia_maes", "max"),
                 dia_pais=("dia_pais", "max"),
                 dia_criancas=("dia_criancas", "max"),
                 black_friday=("black_friday", "max"),
                 natal=("natal", "max"),
             )
             .reset_index()
             .rename(columns={"date": "week_start"})
    )

    # ONE-HOT semanal (presença na semana) para TOP_K brands/categories
    df["week_start"] = df["sale_date"] - pd.to_timedelta(df["sale_date"].dt.weekday, unit="D")

    top_brands = (df.groupby("brand_name")["revenue"].sum()
                    .sort_values(ascending=False).head(TOP_K).index.tolist()
                    if "brand_name" in df.columns else [])
    top_cats   = (df.groupby("category_name")["revenue"].sum()
                    .sort_values(ascending=False).head(TOP_K).index.tolist()
                    if "category_name" in df.columns else [])

    # ---- Marcas (presença semanal) ----
    if top_brands:
        brand_cols = {b: f"brand__{slugify(b)}" for b in top_brands}
        brand_week = (
            df.assign(val=1)
              .loc[df["brand_name"].isin(top_brands), ["week_start", "brand_name", "val"]]
              .drop_duplicates()
              .pivot_table(index="week_start", columns="brand_name", values="val", aggfunc="max")
              .fillna(0.0)
              .rename(columns=brand_cols)
              .reset_index()
        )
        weekly = weekly.merge(brand_week, on="week_start", how="left")
    else:
        brand_cols = {}

    # ---- Categorias (presença semanal) ----
    if top_cats:
        cat_cols = {c: f"cat__{slugify(c)}" for c in top_cats}
        cat_week = (
            df.assign(val=1)
              .loc[df["category_name"].isin(top_cats), ["week_start", "category_name", "val"]]
              .drop_duplicates()
              .pivot_table(index="week_start", columns="category_name", values="val", aggfunc="max")
              .fillna(0.0)
              .rename(columns=cat_cols)
              .reset_index()
        )
        weekly = weekly.merge(cat_week, on="week_start", how="left")
    else:
        cat_cols = {}

    # ---- Tratamento ROBUSTO dos dummies (EVITA KeyError) ----
    dummy_cols = list(brand_cols.values()) + list(cat_cols.values())

    # 1) Cria explicitamente as colunas dummies que estiverem faltando
    for c in dummy_cols:
        if c not in weekly.columns:
            weekly[c] = 0.0

    # 2) Só faz fillna nas colunas que existem no DataFrame
    existing = [c for c in dummy_cols if c in weekly.columns]
    if existing:
        weekly[existing] = weekly[existing].fillna(0.0)

    # Salvar CSVs
    df.to_csv(CSV_LINE, index=False)
    daily.to_csv(CSV_DAILY, index=False)
    weekly.to_csv(CSV_WEEKLY, index=False)

    # Heatmap de correlação (diário)
    numcols = daily.select_dtypes(include=[np.number]).columns
    if len(numcols) >= 2:
        corr = daily[numcols].corr()
        plt.figure(figsize=(9, 6))
        plt.imshow(corr, interpolation="nearest")
        plt.title("Correlação (diário)")
        plt.xticks(range(len(numcols)), numcols, rotation=45, ha="right")
        plt.yticks(range(len(numcols)), numcols)
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(PNG_CORR, dpi=140)
        plt.close()

    meta = {
        "top_brands": top_brands,
        "top_categories": top_cats,
        "brand_dummy_cols": list(brand_cols.values()),
        "cat_dummy_cols": list(cat_cols.values())
    }
    return df, daily, weekly, meta

# --------- 3) FEATURES TEMPORAIS + SPLIT SEM VAZAMENTO ------------
def criar_features_temporais(df_agg: pd.DataFrame, date_col: str, target_col: str, add_lags=True):
    d = df_agg.copy()
    d[date_col]   = pd.to_datetime(d[date_col])
    d["year"]     = d[date_col].dt.year
    d["month"]    = d[date_col].dt.month
    d["day"]      = d[date_col].dt.day
    d["weekday"]  = d[date_col].dt.weekday  # 0=segunda

    seasonal_cols = [
        "volta_as_aulas","carnaval","semana_santa","sao_joao",
        "dia_namorados","dia_maes","dia_pais","dia_criancas",
        "black_friday","natal"
    ]
    for c in seasonal_cols:
        if c not in d.columns:
            d[c] = 0

    dummy_cols = [c for c in d.columns if c.startswith("brand__") or c.startswith("cat__")]

    d = d.sort_values(date_col).reset_index(drop=True)
    if add_lags and len(d) >= 5:
        d["lag1"] = d[target_col].shift(1)
        d["lag2"] = d[target_col].shift(2)
        d["ma3"]  = d[target_col].rolling(3).mean()
    else:
        d["lag1"] = np.nan
        d["lag2"] = np.nan
        d["ma3"]  = np.nan

    d = d.dropna().reset_index(drop=True)

    features = ["year","month","day","weekday", *seasonal_cols, "lag1","lag2","ma3", *dummy_cols]
    features = [c for c in features if c in d.columns]
    X = d[features].copy()
    y = d[target_col].copy()
    return X, y, d, features

def split_temporal(X: pd.DataFrame, y: pd.Series, train_ratio=0.8):
    n = len(X)
    cut = max(1, int(n * train_ratio))
    X_train, X_test = X.iloc[:cut], X.iloc[cut:]
    y_train, y_test = y.iloc[:cut], y.iloc[cut:]
    return X_train, X_test, y_train, y_test

# ----------------------- 4) MODELO + MÉTRICAS ----------------------
def treinar_modelo(X_train, y_train):
    if HAS_XGB:
        model = XGBRegressor(
            n_estimators=400,
            learning_rate=0.08,
            max_depth=4,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            n_jobs=-1
        )
    else:
        model = GradientBoostingRegressor(
            n_estimators=400,
            learning_rate=0.08,
            max_depth=3,
            random_state=42
        )
    model.fit(X_train, y_train)
    return model

def avaliar_modelo(model, X_test, y_test, features):
    if len(X_test) == 0:
        return {"warning": "Sem dados de teste para avaliar."}

    y_pred = model.predict(X_test)
    #rmse = mean_squared_error(y_test, y_pred, squared=False)
    # Compatibilidade com versões antigas do sklearn: some versions don't accept 'squared' kwarg
    try:
        rmse = mean_squared_error(y_test, y_pred, squared=False)
    except TypeError:
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    mae  = mean_absolute_error(y_test, y_pred)
    mape = (np.abs((y_test - y_pred) / np.maximum(np.abs(y_test), 1e-9)).mean()) * 100.0

    # Real vs Previsto
    plt.figure(figsize=(9, 4))
    plt.plot(y_test.values, label="Real")
    plt.plot(y_pred, label="Previsto")
    plt.title("Real vs Previsto (ordem temporal do teste)")
    plt.xlabel("Índice temporal (teste)")
    plt.ylabel("Vendas agregadas")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PNG_AVP, dpi=140)
    plt.close()

    # Importância das features (se disponível)
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        order = np.argsort(imp)[::-1]
        plt.figure(figsize=(9, 5))
        plt.bar(range(len(order)), imp[order])
        plt.xticks(range(len(order)), np.array(features)[order], rotation=45, ha="right")
        plt.title("Importância das Features")
        plt.tight_layout()
        plt.savefig(PNG_FIMP, dpi=140)
        plt.close()

    return {"rmse": rmse, "mae": mae, "mape": mape, "n_test": len(y_test)}

# ------------------------------- MAIN ------------------------------
if __name__ == "__main__":
    # 1) Exporta do SQLite para CSV joinado
    df_joined = exportar_joinado(DB_PATH, CSV_JOINED)
    #df_joined = pd.read_csv('./sales_saleitem_synthetic_joined.csv')

    # 2) Prepara dados + flags sazonais + one-hot semanal
    df_line, df_daily, df_weekly, meta = preparar_dados(df_joined)
    df_line, df_daily, df_weekly, meta = preparar_dados(df_joined)

    # 3) Nível de previsão: semanal é mais estável em varejo
    base = df_weekly.rename(columns={"week_start": "date", "total_revenue": "y"})

    # 4) Cria features + split temporal (sem vazamento)
    if len(base) < 5:
        print(f"[!] Histórico semanal curto ({len(base)} linhas). Resultados podem ser instáveis.")
    else:
        X, y, df_feat, features = criar_features_temporais(base, date_col="date", target_col="y", add_lags=True)
        if len(X) < 5:
            print("[!] Após criar lags/MA e remover NaNs, sobraram poucas linhas para treino. "
                  "Amplie o histórico ou use add_lags=False.")
        else:
            X_train, X_test, y_train, y_test = split_temporal(X, y, train_ratio=0.8)
            model = treinar_modelo(X_train, y_train)
            metrics = avaliar_modelo(model, X_test, y_test, features)

            # 5) Salva dataset de features para auditoria
            df_feat.to_csv(os.path.join(OUT_DIR, "weekly_features_dataset.csv"), index=False)

            # 6) Logs resumo
            print("\n>>> RESUMO")
            print("TOP marcas:", meta.get("top_brands"))
            print("TOP categorias:", meta.get("top_categories"))
            print("Features usadas:", features)
            print("Métricas:", metrics)
