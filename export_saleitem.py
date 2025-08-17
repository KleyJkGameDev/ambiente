#!/usr/bin/env python3
"""
export_saleitems_join.py

Uso:
    python export_saleitems_join.py /caminho/para/db.sqlite3

O script:
 - Lista tabelas e colunas
 - Detecta automaticamente colunas "nome/título/description" nas tabelas relacionadas
 - Monta um JOIN entre sales_saleitem e products_* e sales_sale
 - Exporta sales_saleitem_joined.csv no diretório atual
"""

import sqlite3
import sys
import os

try:
    import pandas as pd
except Exception:
    pd = None

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "db.sqlite3"
OUT_CSV = "sales_saleitem_joined.csv"

PREFERRED_NAME_COLS = [
    "name", "nome", "title", "titulo", "product_name", "product", "description",
    "descricao", "desc"
]
PREFERRED_DATE_COLS = ["created_at", "created", "date", "sale_date", "created_on"]

def connect(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Banco não encontrado em: {path}")
    return sqlite3.connect(path)

def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    return [r[0] for r in cur.fetchall()]

def table_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    rows = cur.fetchall()
    # rows: (cid, name, type, notnull, dflt_value, pk)
    return [r[1] for r in rows]

def pick_preferred(col_list, preferred_names):
    lower_map = {c.lower(): c for c in col_list}
    for pref in preferred_names:
        if pref in lower_map:
            return lower_map[pref]
    # fallback: choose first text-like column (heuristic)
    for c in col_list:
        if any(k in c.lower() for k in ("name", "title", "desc", "produto", "categoria", "brand")):
            return c
    return None

def safe_ident(name, valid_list):
    """Retorna name se estiver em valid_list; caso contrário None"""
    if name and name in valid_list:
        return name
    return None

def main():
    try:
        conn = connect(DB_PATH)
    except Exception as e:
        print("Erro ao abrir o banco:", e)
        return

    print("Conectado em:", DB_PATH)
    tables = list_tables(conn)
    print("\nTabelas encontradas:")
    for t in tables:
        print(" -", t)

    needed = ["sales_saleitem", "products_product", "products_category", "products_brand", "sales_sale"]
    print("\nVerificando existência das tabelas necessárias...")
    for n in needed:
        if n not in tables:
            print(f"AVISO: tabela '{n}' não encontrada. O script vai tentar prosseguir com os que existem.")

    # Colunas
    cols = {}
    for t in needed:
        if t in tables:
            cols[t] = table_columns(conn, t)
        else:
            cols[t] = []

    print("\nColunas detectadas (resumido):")
    for t, c in cols.items():
        print(f" - {t}: {', '.join(c) if c else '(não encontrada)'}")

    # Detectar colunas "nome" para produto/categoria/marca
    prod_name = pick_preferred(cols.get("products_product", []), PREFERRED_NAME_COLS)
    cat_name = pick_preferred(cols.get("products_category", []), PREFERRED_NAME_COLS)
    brand_name = pick_preferred(cols.get("products_brand", []), PREFERRED_NAME_COLS)
    sale_date = pick_preferred(cols.get("sales_sale", []), PREFERRED_DATE_COLS)

    print("\nColunas escolhidas para leitura:")
    print(" - produto:", prod_name or "(não encontrada - usarei product_id)")
    print(" - categoria:", cat_name or "(não encontrada - usarei category_id)")
    print(" - marca:", brand_name or "(não encontrada - usarei brand_id)")
    print(" - data da venda:", sale_date or "(não encontrada - usarei sale_id)")

    # Montar SELECT dinamicamente, sempre verificando que a coluna existe
    si_cols = cols.get("sales_saleitem", [])
    base_select = []
    # incluir campos do saleitem
    for want in ["id", "quantity", "price_at_sale", "created_at", "updated_at",
                 "brand_id", "product_id", "sale_id", "category_id"]:
        if want in si_cols:
            base_select.append(f"si.{want} AS {want}")

    # campos dos relacionamentos (apenas se tabelas existirem)
    joins = []
    if "products_product" in tables:
        if prod_name:
            base_select.append(f"p.{prod_name} AS product_name")
        else:
            base_select.append("p.id AS product_id")
        joins.append("JOIN products_product p ON si.product_id = p.id")
    if "products_category" in tables:
        if cat_name:
            base_select.append(f"c.{cat_name} AS category_name")
        else:
            base_select.append("c.id AS category_id")
        joins.append("LEFT JOIN products_category c ON si.category_id = c.id")
    if "products_brand" in tables:
        if brand_name:
            base_select.append(f"b.{brand_name} AS brand_name")
        else:
            base_select.append("b.id AS brand_id")
        joins.append("LEFT JOIN products_brand b ON si.brand_id = b.id")
    if "sales_sale" in tables:
        if sale_date:
            base_select.append(f"s.{sale_date} AS sale_date")
        else:
            base_select.append("s.id AS sale_id")
        joins.append("JOIN sales_sale s ON si.sale_id = s.id")

    select_clause = ",\n    ".join(base_select) if base_select else "si.*"
    join_clause = "\n".join(joins)

    query = f"""
    SELECT
        {select_clause}
    FROM sales_saleitem si
    {join_clause}
    ORDER BY si.id;
    """

    print("\nQuery gerada:\n")
    print(query)

    # Executar e exportar
    try:
        if pd is not None:
            df = pd.read_sql_query(query, conn)
            df.to_csv(OUT_CSV, index=False)
            print(f"\nExportado para CSV: {os.path.abspath(OUT_CSV)} (linhas: {len(df)})")
        else:
            # fallback sem pandas
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            cols_names = [d[0] for d in cur.description] if cur.description else []
            import csv
            with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if cols_names:
                    w.writerow(cols_names)
                w.writerows(rows)
            print(f"\nExportado para CSV: {os.path.abspath(OUT_CSV)} (linhas: {len(rows)})")
    except Exception as e:
        print("Erro ao executar query/exportar:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
