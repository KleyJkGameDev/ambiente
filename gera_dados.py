# (INÍCIO do arquivo — este é o seu gera_dados.py modificado)
#!/usr/bin/env python3
"""
generate_50k_brazil_sales.py - versão com timestamps realistas

Gera ~50k saleitems realistas considerando sazonalidade do Brasil e feriados nacionais.
As datas created_at/updated_at são distribuídas aleatoriamente considerando picos e feriados.
"""
import sqlite3
import random
import math
from datetime import datetime, timedelta, date, time
import os
import sys
import csv

try:
    import pandas as pd
except Exception:
    pd = None

# ---------------- CONFIG ----------------
TARGET_SALEITEMS = 50000
NUM_PRODUCTS = 800           # tamanho do catálogo (se já existirem, completa até esse número)
PERIOD_DAYS = 730            # janela (dias) para distribuir as vendas atrás (2 anos)
SEED = 2025
BATCH_COMMIT = 1000         # commits a cada N inserts para performance
MIN_ITEMS_PER_SALE = 1
MAX_ITEMS_PER_SALE = 10
OUT_CSV = "sales_saleitem_synthetic_joined.csv"
# multipliers (ajuste se quiser mais/menos picos)
HOLIDAY_MULTIPLIER = 3.5
BLACKFRIDAY_MULTIPLIER = 6.0
WEEKEND_MULTIPLIER = 1.35
PROMO_PROB = 0.09
# ----------------------------------------

random.seed(SEED)

# ---------- helpers ----------
def connect(db_path):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco não encontrado: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # performance pragmas (temporário) - bom para inserções grandes
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA synchronous = OFF;")
        cur.execute("PRAGMA journal_mode = MEMORY;")
    except:
        pass
    return conn

def table_info(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    return cur.fetchall()

def find_preferred(cols, prefs):
    lower = {c[1].lower(): c[1] for c in cols}
    for p in prefs:
        if p in lower:
            return lower[p]
    for c in cols:
        name = c[1].lower()
        if any(k in name for k in ("name","title","descricao","description","produto")):
            return c[1]
    return None

def find_price_col(cols):
    lower = {c[1].lower(): c[1] for c in cols}
    for p in ("price","preco","valor","unit_price","price_at_sale"):
        if p in lower:
            return lower[p]
    for c in cols:
        n = c[1].lower()
        if "price" in n or "preco" in n or "valor" in n:
            return c[1]
    return None

def find_total_col(cols):
    lower = {c[1].lower(): c[1] for c in cols}
    for p in ("total","amount","valor","order_total","sale_total"):
        if p in lower:
            return lower[p]
    return None

def lognormal_price_by_group():
    # gera preço com grupos cheap/mid/premium para mais realismo
    group = random.choices([0,1,2], weights=[0.72,0.24,0.04])[0]
    if group == 0:
        return round(random.lognormvariate(2.0, 0.45), 2)   # ~3-40
    if group == 1:
        return round(random.lognormvariate(3.0, 0.5), 2)    # ~20-200
    return round(random.lognormvariate(4.2, 0.6), 2)       # premium

# default value generator for NOT NULL columns
def default_value_for_column(col_name, col_type, idx=0, start_date=None, end_date=None):
    lc = (col_name or "").lower()
    t = (col_type or "").lower()
    # booleans / flags
    if "is_active" in lc or lc == "active" or "enabled" in lc or lc.startswith("is_"):
        return 1
    # nomes/titles
    if "name" in lc or "title" in lc:
        return f"Produto_{idx+1:04d}"
    # preço
    if any(k in lc for k in ("price","preco","valor","unit_price")) or "numeric" in t or "real" in t or "decimal" in t:
        return lognormal_price_by_group()
    # timestamps -> criar data aleatória dentro do intervalo se informado
    if "created" in lc or "date" in lc or "timestamp" in lc or "time" in lc:
        if start_date is not None and end_date is not None:
            # random entre start_date - 365d e end_date
            early = start_date - timedelta(days=365)
            span = max(1, (end_date - early).days)
            rnd = early + timedelta(days=random.randint(0, span))
            # adicionar hora aleatória
            dt = datetime.combine(rnd, time(hour=random.randint(0,23), minute=random.randint(0,59), second=random.randint(0,59)))
            return dt.isoformat(sep=' ')
        else:
            return datetime.utcnow().isoformat(sep=' ')
    # integers / ids
    if "int" in t or lc.endswith("_id") or lc == "id":
        return 0
    # texto genérico
    if "char" in t or "text" in t or "varchar" in t:
        return ""
    # fallback
    return ""

# Easter algorithm (Anonymous Gregorian) -> returns date
def easter_date(year):
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

def get_brazil_holidays(start_date, end_date):
    """Return set of date objects for Brazilian national holidays + movable ones in range."""
    holidays = set()
    years = set([ (start_date + timedelta(days=i)).year for i in range((end_date - start_date).days + 1) ])
    # Fixed-date national holidays:
    fixed = [(1,1),   # Ano Novo
             (4,21),  # Tiradentes
             (5,1),   # Dia do Trabalhador
             (9,7),   # Independência
             (10,12), # Nossa Sra Aparecida
             (11,2),  # Finados
             (11,15), # Proclamação da República
             (12,25)] # Natal
    for y in years:
        for m,d in fixed:
            holidays.add(date(y,m,d))
        # movable
        eas = easter_date(y)
        # Carnaval: 47 dias antes da Páscoa (terça-feira de carnaval)
        carnaval = eas - timedelta(days=47)
        # Sexta-feira Santa
        good_friday = eas - timedelta(days=2)
        # Corpus Christi: 60 days after Easter
        corpus_christi = eas + timedelta(days=60)
        holidays.update([eas, carnaval, good_friday, corpus_christi])
    # Black Friday: take 4th friday of November for each year (Brazil)
    for y in years:
        nov1 = date(y,11,1)
        offset = (4 - nov1.weekday()) % 7
        first_friday = nov1 + timedelta(days=offset)
        fourth_friday = first_friday + timedelta(days=21)
        holidays.add(fourth_friday)
    holidays_in_range = set([d for d in holidays if start_date <= d <= end_date])
    return holidays_in_range

def build_day_weights(start_date, period_days, holidays_set):
    """Return list of normalized weights for days 0..period_days-1 (0=oldest day)"""
    weights = []
    for i in range(period_days):
        day_date = start_date + timedelta(days=i)
        # base seasonal (sin wave) stronger amplitude
        doy = day_date.timetuple().tm_yday
        season = 1.0 + 0.6 * math.sin(2*math.pi*(doy/365.0) - 0.15)  # stronger amplitude
        # weekend effect (Sat=5 Sun=6)
        weekday = day_date.weekday()
        weekend = WEEKEND_MULTIPLIER if weekday in (5,6) else 1.0
        w = season * weekend
        # holiday boost
        if day_date in holidays_set:
            if day_date.month == 11 and day_date.weekday() == 4:
                w *= BLACKFRIDAY_MULTIPLIER
            else:
                w *= HOLIDAY_MULTIPLIER
        weights.append(max(0.0001, w))
    s = sum(weights)
    return [x/s for x in weights]

def weighted_choice_index(weights):
    r = random.random()
    cum = 0.0
    for i,w in enumerate(weights):
        cum += w
        if r <= cum:
            return i
    return len(weights)-1

# ---------------- main ----------------
def main(db_path):
    conn = connect(db_path)
    cur = conn.cursor()

    # required tables we try to use/modify
    needed = ["sales_saleitem", "sales_sale", "products_product", "products_category", "products_brand"]
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = set(r[0] for r in cur.fetchall())
    present = {t: (t in tables) for t in needed}
    print("Tabelas presentes:", present)

    # read schemas
    schemas = {}
    for t in needed:
        if t in tables:
            schemas[t] = table_info(conn, t)
        else:
            schemas[t] = []

    prod_name_col = find_preferred(schemas.get("products_product", []), ["name","nome","title"])
    prod_price_col = find_price_col(schemas.get("products_product", []))
    cat_name_col = find_preferred(schemas.get("products_category", []), ["name","nome","title"])
    brand_name_col = find_preferred(schemas.get("products_brand", []), ["name","nome","title"])
    sale_total_col = find_total_col(schemas.get("sales_sale", []))
    sale_date_col = find_preferred(schemas.get("sales_sale", []), ["created_at","created","date","sale_date"])

    print("Detectadas colunas:")
    print(" product name:", prod_name_col, "price:", prod_price_col)
    print(" category name:", cat_name_col, "brand name:", brand_name_col)
    print(" sales_sale total:", sale_total_col, " date:", sale_date_col)

    # build date range EARLY so we can use for product created_at too
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=PERIOD_DAYS-1)
    # product creation range start (allow some products older than start_date)
    product_early = start_date - timedelta(days=365)

    # ensure products exist up to NUM_PRODUCTS
    product_ids = []
    if present["products_product"]:
        cur.execute("SELECT id FROM products_product")
        product_ids = [r[0] for r in cur.fetchall()]
    if present["products_product"] and len(product_ids) < NUM_PRODUCTS:
        to_create = NUM_PRODUCTS - len(product_ids)
        print(f"Inserindo {to_create} produtos sintéticos (com preços log-normal)...")
        prod_schema = schemas['products_product']  # list of tuples
        cols = [c[1] for c in prod_schema if c[5] == 0]  # not pk
        # detect required columns (NOT NULL and no default)
        required_cols = [c[1] for c in prod_schema if c[3] == 1 and c[4] is None and c[5] == 0]
        inserted = []
        for i in range(to_create):
            data = {}
            for col in cols:
                low = col.lower()
                # prefer to set friendly columns first
                if prod_name_col and col == prod_name_col:
                    data[col] = f"Produto_{len(product_ids)+i+1:04d}"
                elif prod_price_col and col == prod_price_col:
                    data[col] = lognormal_price_by_group()
                # created/updated -> escolher data aleatória coerente
                elif "created" in low or "date" in low:
                    # random entre product_early e end_date (com hora aleatória)
                    span_days = max(1, (end_date - product_early).days)
                    rnd_day = product_early + timedelta(days=random.randint(0, span_days))
                    dt = datetime.combine(rnd_day, time(hour=random.randint(0,23), minute=random.randint(0,59), second=random.randint(0,59)))
                    data[col] = dt.isoformat(sep=' ')
                # if column is required and still not set, provide a default value
                elif col in required_cols and col not in data:
                    # find type
                    col_info = next((r for r in prod_schema if r[1] == col), None)
                    col_type = col_info[2] if col_info else None
                    data[col] = default_value_for_column(col, col_type, i, start_date=product_early, end_date=end_date)
                else:
                    # leave optional columns null (not included in INSERT)
                    pass

            # ensure required cols are present (double-check)
            for rc in required_cols:
                if rc not in data:
                    col_info = next((r for r in prod_schema if r[1] == rc), None)
                    col_type = col_info[2] if col_info else None
                    data[rc] = default_value_for_column(rc, col_type, i, start_date=product_early, end_date=end_date)

            to_cols = [c for c in data.keys() if data[c] is not None]
            if not to_cols:
                cur.execute("INSERT INTO products_product DEFAULT VALUES")
            else:
                placeholders = ",".join("?" for _ in to_cols)
                cols_sql = ",".join(to_cols)
                cur.execute(f"INSERT INTO products_product ({cols_sql}) VALUES ({placeholders})", tuple(data[c] for c in to_cols))
            inserted.append(cur.lastrowid)
        conn.commit()
        product_ids.extend(inserted)
        print("Produtos totais agora:", len(product_ids))
    else:
        print("Produtos existentes:", len(product_ids))

    # ensure categories/brands
    def ensure_rows(table, base, count=12):
        if table not in tables:
            return []
        cur.execute(f"SELECT id FROM {table}")
        rows = [r[0] for r in cur.fetchall()]
        if rows:
            return rows
        print(f"Inserindo {count} linhas em {table}")
        schema = schemas[table]
        cols = [c[1] for c in schema if c[5] == 0]
        required_cols = [c[1] for c in schema if c[3] == 1 and c[4] is None and c[5] == 0]
        inserted = []
        for i in range(count):
            data = {}
            for col in cols:
                low = col.lower()
                if "name" in low:
                    data[col] = f"{base}_{i+1}"
                elif "created" in low or "date" in low:
                    # random created_at between product_early and end_date
                    span_days = max(1, (end_date - product_early).days)
                    rnd_day = product_early + timedelta(days=random.randint(0, span_days))
                    dt = datetime.combine(rnd_day, time(hour=random.randint(0,23), minute=random.randint(0,59), second=random.randint(0,59)))
                    data[col] = dt.isoformat(sep=' ')
                elif col in required_cols and col not in data:
                    # supply default for required columns
                    col_info = next((r for r in schema if r[1] == col), None)
                    col_type = col_info[2] if col_info else None
                    data[col] = default_value_for_column(col, col_type, i, start_date=product_early, end_date=end_date)
            # ensure any required col is present
            for rc in required_cols:
                if rc not in data:
                    col_info = next((r for r in schema if r[1] == rc), None)
                    col_type = col_info[2] if col_info else None
                    data[rc] = default_value_for_column(rc, col_type, i, start_date=product_early, end_date=end_date)
            to_cols = [c for c in data.keys() if data[c] is not None]
            if not to_cols:
                cur.execute(f"INSERT INTO {table} DEFAULT VALUES")
            else:
                placeholders = ",".join("?" for _ in to_cols)
                cols_sql = ",".join(to_cols)
                cur.execute(f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})", tuple(data[c] for c in to_cols))
            inserted.append(cur.lastrowid)
        conn.commit()
        return inserted

    cat_ids = ensure_rows("products_category", "Categoria", 12) if present["products_category"] else []
    brand_ids = ensure_rows("products_brand", "Marca", 12) if present["products_brand"] else []

    # read product metadata to base prices and optional mapping of brand/category per product
    product_meta = {}
    if present["products_product"]:
        read_cols = ["id"]
        if prod_name_col: read_cols.append(prod_name_col)
        if prod_price_col: read_cols.append(prod_price_col)
        # try detect brand/category fields inside product table
        field_names = [c[1].lower() for c in schemas['products_product']]
        if "brand_id" in field_names:
            read_cols.append("brand_id")
        if "category_id" in field_names:
            read_cols.append("category_id")
        cur.execute(f"SELECT {','.join(read_cols)} FROM products_product")
        for r in cur.fetchall():
            rid = r[0]
            meta = {}
            try:
                if prod_name_col:
                    meta['name'] = r[read_cols.index(prod_name_col)]
            except: pass
            try:
                if prod_price_col:
                    val = r[read_cols.index(prod_price_col)]
                    meta['price'] = float(val) if val is not None else None
            except: meta['price'] = None
            if "brand_id" in read_cols:
                try: meta['brand_id'] = r[read_cols.index("brand_id")]
                except: meta['brand_id'] = None
            if "category_id" in read_cols:
                try: meta['category_id'] = r[read_cols.index("category_id")]
                except: meta['category_id'] = None
            product_meta[rid] = meta

    # build product list and zipf weights
    product_list = list(product_meta.keys()) if product_meta else product_ids
    if not product_list:
        raise RuntimeError("Nenhum produto disponível para gerar saleitems.")
    nprod = len(product_list)
    # zipf weights
    def zipf_weights(n, s=1.12):
        w = [1.0/((r+1)**s) for r in range(n)]
        ssum = sum(w)
        return [x/ssum for x in w]
    weights = zipf_weights(nprod, s=1.12)

    # build date weights with Brazilian holidays
    # (re-use start_date/end_date defined above)
    holidays = get_brazil_holidays(start_date, end_date)
    day_weights = build_day_weights(start_date, PERIOD_DAYS, holidays)

    # prepare for insertion loop, create sales and attach items until target reached
    price_cols_si = [c[1] for c in schemas.get("sales_saleitem", [])]
    # detect price column in saleitem table
    si_price_col = None
    for c in price_cols_si:
        if c.lower().startswith("price"):
            si_price_col = c
            break

    # create sale entries as needed; we'll create sales incrementally and insert items
    inserted_items = 0
    sale_ids = []
    created_sales = 0

    # to speed: pre-generate cumulative weights
    cum_weights = []
    s = 0.0
    for w in day_weights:
        s += w
        cum_weights.append(s)

    def choose_day_index():
        r = random.random()
        # binary search for speed
        lo = 0; hi = len(cum_weights)-1
        while lo < hi:
            mid = (lo+hi)//2
            if r <= cum_weights[mid]:
                hi = mid
            else:
                lo = mid+1
        return lo

    # prepare sale columns
    sale_cols = [c[1] for c in schemas.get("sales_sale", [])]

    # Batch insertion helpers
    sale_insert_stmt = None
    si_insert_stmt = None

    cur = conn.cursor()
    batch_counter = 0

    print("Iniciando inserção visando", TARGET_SALEITEMS, "saleitems...")
    # loop until target reached
    while inserted_items < TARGET_SALEITEMS:
        # create one sale
        day_idx = choose_day_index()
        sale_dt = start_date + timedelta(days=day_idx)
        # add random time within day
        sale_datetime = datetime.combine(sale_dt, time(hour=random.randint(8,22), minute=random.randint(0,59), second=random.randint(0,59)))
        # insert sale - put sale_date if detected
        sale_data = {}
        if sale_date_col and sale_date_col in sale_cols:
            sale_data[sale_date_col] = sale_datetime.isoformat(sep=' ')
        if sale_data:
            cur.execute(f"INSERT INTO sales_sale ({','.join(sale_data.keys())}) VALUES ({','.join('?' for _ in sale_data)})", tuple(sale_data.values()))
        else:
            cur.execute("INSERT INTO sales_sale DEFAULT VALUES")
        sid = cur.lastrowid
        sale_ids.append(sid)
        created_sales += 1

        # decide number of items for this sale (skewed distribution)
        # majority 1-2, tail to MAX_ITEMS_PER_SALE
        r = random.random()
        if r < 0.6:
            k = 1
        elif r < 0.85:
            k = random.randint(2,3)
        elif r < 0.96:
            k = random.randint(4,6)
        else:
            k = random.randint(7, MAX_ITEMS_PER_SALE)

        for _ in range(k):
            # choose product by weighted popularity
            pid = random.choices(product_list, weights=weights, k=1)[0]
            pmeta = product_meta.get(pid, {})
            # quantity mostly 1
            q_r = random.random()
            if q_r < 0.8:
                qty = 1
            elif q_r < 0.95:
                qty = random.randint(2,3)
            else:
                qty = random.randint(4,12)
            # price logic
            base = pmeta.get('price') if pmeta and pmeta.get('price') else lognormal_price_by_group()
            # promotional chance higher on promo days (we already boosted day weights); still apply discount occasionally
            discount = 0.0
            if random.random() < PROMO_PROB:
                discount = round(random.uniform(0.05, 0.50), 2)
            noise = random.uniform(-0.025, 0.03)
            price_at_sale = round(max(0.01, base * (1 - discount) * (1 + noise)), 2)

            # === UPDATED: created_at/updated_at agora são baseados em sale_datetime com jitter ===
            # Datas iguais para cada linha
            created_at = sale_datetime.isoformat(sep=' ')
            updated_at = sale_datetime.isoformat(sep=' ')


            # build saleitem values depending on actual columns present
            si_values = {}
            if "product_id" in price_cols_si:
                si_values["product_id"] = pid
            if "sale_id" in price_cols_si:
                si_values["sale_id"] = sid
            # quantity column names may vary, try 'quantity' else check similar
            if "quantity" in price_cols_si:
                si_values["quantity"] = qty
            else:
                # try to find any likely quantity column
                for c in price_cols_si:
                    if "qty" in c.lower():
                        si_values[c] = qty
                        break
            if si_price_col:
                si_values[si_price_col] = price_at_sale
            # timestamps: use created_at/updated_at values (not current utc)
            for c in price_cols_si:
                lc = c.lower()
                if lc in ("created_at","created","createdon"):
                    si_values[c] = created_at
                if lc in ("updated_at","updated"):
                    si_values[c] = updated_at
            # optional brand/category assignment
            if "brand_id" in price_cols_si:
                bid = pmeta.get("brand_id") or (random.choice(brand_ids) if brand_ids else None)
                if bid:
                    si_values["brand_id"] = bid
            if "category_id" in price_cols_si:
                cid = pmeta.get("category_id") or (random.choice(cat_ids) if cat_ids else None)
                if cid:
                    si_values["category_id"] = cid
            # insert saleitem
            if si_values:
                cur.execute(f"INSERT INTO sales_saleitem ({','.join(si_values.keys())}) VALUES ({','.join('?' for _ in si_values)})", tuple(si_values.values()))
                inserted_items += 1
                batch_counter += 1

            # commit in batches
            if batch_counter >= BATCH_COMMIT:
                conn.commit()
                batch_counter = 0
                print(f"Progress: {inserted_items}/{TARGET_SALEITEMS} saleitems inserted...")

            if inserted_items >= TARGET_SALEITEMS:
                break

        # end of sale loop

    # final commit
    if batch_counter > 0:
        conn.commit()

    print("Inserção finalizada. Saleitems inseridos:", inserted_items, " em vendas:", created_sales)

    # (rest of script unchanged: update totals, export CSV, summaries)
    # update sale totals if column exists
    if sale_total_col and sale_total_col in [c[1] for c in schemas.get("sales_sale", [])]:
        print("Atualizando total das vendas na coluna:", sale_total_col)
        # detect price col in saleitem table again
        si_price_cols = [c[1] for c in schemas.get("sales_saleitem", [])]
        price_col = None
        for c in si_price_cols:
            if c.lower().startswith("price"):
                price_col = c
                break
        if price_col:
            # batch update (inefficient but ok)
            for sid in sale_ids:
                cur.execute(f"SELECT quantity, {price_col} FROM sales_saleitem WHERE sale_id = ?", (sid,))
                rows = cur.fetchall()
                total = 0.0
                for r in rows:
                    q = r[0] if r[0] is not None else 1
                    p = r[1] if r[1] is not None else 0.0
                    try:
                        total += float(q) * float(p)
                    except:
                        pass
                try:
                    cur.execute(f"UPDATE sales_sale SET {sale_total_col} = ? WHERE id = ?", (round(total,2), sid))
                except Exception:
                    pass
            conn.commit()
            print("Totais atualizados.")
        else:
            print("Não detectei coluna de preço em sales_saleitem; pulei atualização de total.")
    else:
        print("Coluna de total da venda não encontrada; pulando atualização.")

    # export joined CSV for inspection
    print("Exportando CSV de inspeção:", OUT_CSV)
    join_select = ["si.id AS id"]
    si_cols = [c[1] for c in schemas.get("sales_saleitem", [])]
    for cand in ("quantity","price_at_sale","created_at","updated_at"):
        if cand in si_cols:
            join_select.append(f"si.{cand}")
    if present.get("products_product") and prod_name_col:
        join_select.append(f"p.{prod_name_col} AS product_name")
    else:
        join_select.append("si.product_id AS product_id")
    if present.get("products_category"):
        if cat_name_col:
            join_select.append(f"c.{cat_name_col} AS category_name")
        else:
            join_select.append("si.category_id AS category_id")
    if present.get("products_brand"):
        if brand_name_col:
            join_select.append(f"b.{brand_name_col} AS brand_name")
        else:
            join_select.append("si.brand_id AS brand_id")
    if present.get("sales_sale"):
        if sale_date_col:
            join_select.append(f"s.{sale_date_col} AS sale_date")
        else:
            join_select.append("s.id AS sale_id")
        if sale_total_col:
            join_select.append(f"s.{sale_total_col} AS sale_total")

    joins = " FROM sales_saleitem si"
    if present.get("products_product"):
        joins += " LEFT JOIN products_product p ON si.product_id = p.id"
    if present.get("products_category"):
        joins += " LEFT JOIN products_category c ON si.category_id = c.id"
    if present.get("products_brand"):
        joins += " LEFT JOIN products_brand b ON si.brand_id = b.id"
    if present.get("sales_sale"):
        joins += " LEFT JOIN sales_sale s ON si.sale_id = s.id"

    sql = "SELECT " + ", ".join(join_select) + joins + " ORDER BY si.id"
    cur.execute(sql)
    rows = cur.fetchall()
    colnames = [d[0] for d in cur.description] if cur.description else []

    if rows:
        if pd is not None:
            df = pd.DataFrame(rows, columns=colnames)
            df.to_csv(OUT_CSV, index=False)
        else:
            with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(colnames)
                for r in rows:
                    w.writerow([r[c] for c in colnames])
        print("CSV exportado:", os.path.abspath(OUT_CSV), "linhas:", len(rows))
    else:
        print("Nenhuma linha para exportar.")

    # final counts
    for t in ("products_product","products_category","products_brand","sales_sale","sales_saleitem"):
        if t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t}: {cur.fetchone()[0]}")
    conn.close()
    print("Pronto.")

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "db.sqlite3"
    main(db)
# (FIM do arquivo)
