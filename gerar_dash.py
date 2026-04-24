#!/usr/bin/env python3
"""
gerar_dash.py — Gera o dashboard da carteira do Renan
Uso: python gerar_dash.py
Requer: google-cloud-bigquery  (pip install google-cloud-bigquery)
        ou bq CLI autenticado (usa subprocess como fallback)
"""

import json, subprocess, sys, os
from datetime import date, datetime, timedelta

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA CARTEIRA
# ─────────────────────────────────────────────
SELLERS = {
    321353148:  "COUTINHO IMPORTS",
    40228339:   "RJ IMPORTS",
    585892450:  "GUARASOL",
    41157648:   "SR ARCONDICIONADO",
    606480404:  "AKS MULTIMIDIA",
    44163454:   "A01 MULTIMIDIA",
    2412168911: "RECDISTRIBUIDORA",
    241739230:  "NOVAKENNEDY AUTOPEÇAS",
    188890490:  "JAPAPECASSAOPAULO",
    84123998:   "FBR AUTO PARTS",
    126899818:  "KAÇULA PEÇAS",
    7720042:    "SÃO PAULO AUTO PEÇAS",
    80575359:   "BAHDIGITAL",
    117295382:  "BALIAUTOPARTSPARTS",
    1056746654: "COTCOMERCIO",
    250607460:  "PICKUPCOMFORT",
    106084140:  "GOBAUTO",
    97254353:   "LEGERE PARTS",
    416330730:  "PEPE PARTS",
    324410026:  "PRUDENPARTS",
    1989634356: "VALEPARTZ",
    228410552:  "TGF AUTOMOTIVE",
    697936923:  "777 ACESSORIOS",
    118570204:  "SPEEDBIKERSLOJA",
    272371352:  "SPEEDBIKERSLOJA2",
    27387997:   "SUALOJADUASRODASSB",
    463776938:  "SUALOJADUASRODASG",
    183730323:  "UNIVERSO DO CAMINHAO",
    223985238:  "SAMURAIDISTRIBUIDORA",
    710082024:  "AGILE PARTS",
    221832146:  "NOVAESMOTOPEÇAS",
    188510514:  "EXTREME AUDIO",
    293532748:  "EDUARDO MOTOS",
    329489382:  "RR14MOTOPARTS",
    1120706508: "OK PARTS",
    757095392:  "MAX COMPRESSORES TURIK",
    204264030:  "SHOPPART PEÇAS AUTO",
}

IDS_LIST = list(SELLERS.keys())
IDS_STR  = ", ".join(str(x) for x in IDS_LIST)
PROJECT  = "meli-bi-data"
HOJE     = date.today()
ONTEM    = HOJE - timedelta(days=1)
D7       = HOJE - timedelta(days=7)
MTD_INI  = HOJE.replace(day=1)
LY_INI   = MTD_INI.replace(year=MTD_INI.year - 1)
LY_FIM   = ONTEM.replace(year=ONTEM.year - 1)
L30_INI  = HOJE - timedelta(days=30)

def short_name(nome):
    """Nome curto para gráficos (max 14 chars)."""
    palavras = nome.split()
    return palavras[0][:14] if palavras else nome[:14]


# ─────────────────────────────────────────────
# EXECUTA QUERY NO BQ
# ─────────────────────────────────────────────
def bq(sql: str) -> list[dict]:
    """Executa query via bq CLI e retorna lista de dicts."""
    cmd = [
        "bq", "query",
        f"--project_id={PROJECT}",
        "--use_legacy_sql=false",
        "--format=json",
        "--max_rows=10000",
        sql
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[BQ ERROR] {result.stderr[:300]}", file=sys.stderr)
            return []
        out = result.stdout.strip()
        if not out or out == "[]":
            return []
        return json.loads(out)
    except subprocess.TimeoutExpired:
        print("[BQ TIMEOUT]", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[BQ EXCEPTION] {e}", file=sys.stderr)
        return []


def safe_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(v, default=0):
    try:
        return int(float(v)) if v is not None else default
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────
# QUERY 1: GMV DIÁRIO (OVERALL_GENERAL)
# ─────────────────────────────────────────────
def query_gmv_diario():
    print("  → Buscando GMV diário...")
    sql = f"""
    SELECT
      CUS_CUST_ID                                     AS seller_id,
      CALENDAR_DATE                                   AS data,
      SUM(TGMV_LC)                                    AS gmv,
      SUM(TSI)                                        AS tsi,
      MAX(NICKNAME_SELLER)                            AS nickname
    FROM `{PROJECT}.WHOWNER.DM_MKP_COMMERCE_OVERALL_GENERAL`
    WHERE CUS_CUST_ID IN ({IDS_STR})
      AND CALENDAR_DATE BETWEEN '{L30_INI}' AND '{ONTEM}'
      AND SIT_SITE_ID = 'MLB'
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return bq(sql)


# ─────────────────────────────────────────────
# QUERY 2: GMV LY (SAME PERIOD LAST YEAR)
# ─────────────────────────────────────────────
def query_gmv_ly():
    print("  → Buscando GMV LY...")
    sql = f"""
    SELECT
      CUS_CUST_ID     AS seller_id,
      SUM(TGMV_LC)    AS gmv_ly,
      SUM(TSI)        AS tsi_ly
    FROM `{PROJECT}.WHOWNER.DM_MKP_COMMERCE_OVERALL_GENERAL`
    WHERE CUS_CUST_ID IN ({IDS_STR})
      AND CALENDAR_DATE BETWEEN '{LY_INI}' AND '{LY_FIM}'
      AND SIT_SITE_ID = 'MLB'
    GROUP BY 1
    """
    return bq(sql)


# ─────────────────────────────────────────────
# QUERY 3: FULL & LOGÍSTICA
# ─────────────────────────────────────────────
def query_full():
    print("  → Buscando Full & Logística...")
    sql = f"""
    SELECT
      CUS_CUST_ID                                              AS seller_id,
      CALENDAR_DATE                                            AS data,
      SUM(GMV_FBM_LC)                                         AS gmv_full,
      SUM(GMV_XD_LC)                                          AS gmv_xd,
      SUM(GMV_FLEX_LC)                                        AS gmv_flex,
      SUM(GMV_ME2_LC)                                         AS gmv_ds,
      SUM(GMV_FBM_LC + GMV_XD_LC + GMV_FLEX_LC + GMV_ME2_LC) AS gmv_total,
      SUM(SKU_TOTAL_STOCK)                                    AS estoque_total,
      SUM(SKU_KEY_STOCKOUT)                                   AS stockout_skus,
      SUM(SKU_KEY_DOH_FCST_LOWER_2W)                         AS doh_baixo,
      SUM(SKU_GMV_FBM_LC_LOST)                               AS gmv_perdido
    FROM `{PROJECT}.WHOWNER.DM_MKP_COMMERCE_SHIPPING_FBM_DETAIL`
    WHERE CUS_CUST_ID IN ({IDS_STR})
      AND CALENDAR_DATE BETWEEN '{L30_INI}' AND '{ONTEM}'
      AND SIT_SITE_ID = 'MLB'
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return bq(sql)


# ─────────────────────────────────────────────
# QUERY 4: ADS
# ─────────────────────────────────────────────
def query_ads():
    print("  → Buscando ADS...")
    sql = f"""
    SELECT
      CUS_CUST_ID         AS seller_id,
      CALENDAR_DATE       AS data,
      SUM(revenues_pads)  AS invest_pads,
      SUM(revenues_bads)  AS invest_bads,
      SUM(TGMV_LC)        AS gmv_ads
    FROM `{PROJECT}.SBOX_MELI_BI_ADS.BIADS_REVENUESTGMV_ADS_SEGMENTO`
    WHERE CUS_CUST_ID IN ({IDS_STR})
      AND CALENDAR_DATE BETWEEN '{L30_INI}' AND '{ONTEM}'
      AND SIT_SITE_ID = 'MLB'
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return bq(sql)


# ─────────────────────────────────────────────
# PROCESSA E MONTA O OBJETO DATA
# ─────────────────────────────────────────────
def build_data(gmv_rows, gmv_ly_rows, full_rows, ads_rows):
    print("  → Processando dados...")

    # Índices por seller
    gmv_by_seller = {}
    for r in gmv_rows:
        sid = safe_int(r["seller_id"])
        gmv_by_seller.setdefault(sid, []).append(r)

    ly_by_seller = {safe_int(r["seller_id"]): r for r in gmv_ly_rows}

    full_by_seller = {}
    for r in full_rows:
        sid = safe_int(r["seller_id"])
        full_by_seller.setdefault(sid, []).append(r)

    ads_by_seller = {}
    for r in ads_rows:
        sid = safe_int(r["seller_id"])
        ads_by_seller.setdefault(sid, []).append(r)

    sellers_config = [
        {"id": sid, "nome": nome, "short": short_name(nome)}
        for sid, nome in SELLERS.items()
    ]

    sellers_data = {}
    ct_gmv_diario = {}  # data -> gmv total carteira
    ct_mix = {"full": 0, "xd": 0, "flex": 0, "ds": 0}
    ct_gmv_perdido = 0
    ct_stockout = 0
    ct_doh_baixo = 0
    ct_invest_ads = 0
    ct_gmv_ads = 0
    alertas = []

    for sid, nome in SELLERS.items():
        rows_gmv = gmv_by_seller.get(sid, [])
        rows_full = full_by_seller.get(sid, [])
        rows_ads = ads_by_seller.get(sid, [])
        ly = ly_by_seller.get(sid, {})

        # GMV diário
        gmv_diario = []
        gmv_mtd = 0
        gmv_ontem = 0
        gmv_d7 = 0
        tsi_mtd = 0
        for r in sorted(rows_gmv, key=lambda x: x["data"]):
            d = r["data"][:10]
            g = safe_float(r["gmv"])
            t = safe_float(r["tsi"])
            gmv_diario.append({"data": d, "gmv": round(g, 2), "tsi": round(t)})
            if d >= str(MTD_INI):
                gmv_mtd += g
                tsi_mtd += t
            if d == str(ONTEM):
                gmv_ontem = g
            if d == str(D7):
                gmv_d7 = g

        var_d7 = ((gmv_ontem / gmv_d7) - 1) * 100 if gmv_d7 > 0 else None
        gmv_ly_v = safe_float(ly.get("gmv_ly"))
        tsi_ly_v = safe_float(ly.get("tsi_ly"))
        var_yoy = ((gmv_mtd / gmv_ly_v) - 1) * 100 if gmv_ly_v > 0 else None
        ticket = gmv_mtd / tsi_mtd if tsi_mtd > 0 else 0

        # Acumula carteira diário
        for r in rows_gmv:
            d = r["data"][:10]
            g = safe_float(r["gmv"])
            ct_gmv_diario[d] = ct_gmv_diario.get(d, 0) + g

        # Full
        full_gmv_full = 0
        full_gmv_xd = 0
        full_gmv_flex = 0
        full_gmv_ds = 0
        full_estoque = 0
        full_stockout = 0
        full_doh = 0
        full_gmv_perdido = 0
        full_diario = []
        for r in sorted(rows_full, key=lambda x: x["data"]):
            d = r["data"][:10]
            gf = safe_float(r["gmv_full"])
            gx = safe_float(r["gmv_xd"])
            gfl = safe_float(r["gmv_flex"])
            gd = safe_float(r["gmv_ds"])
            full_diario.append({
                "data": d,
                "gmv_full": round(gf, 2), "gmv_xd": round(gx, 2),
                "gmv_flex": round(gfl, 2), "gmv_ds": round(gd, 2)
            })
            if d >= str(MTD_INI):
                full_gmv_full += gf
                full_gmv_xd += gx
                full_gmv_flex += gfl
                full_gmv_ds += gd
            # Estoque, stockout e DOH do dia mais recente
            if d == str(ONTEM):
                full_estoque = safe_int(r["estoque_total"])
                full_stockout = safe_int(r["stockout_skus"])
                full_doh = safe_int(r["doh_baixo"])
                full_gmv_perdido += safe_float(r["gmv_perdido"])

        full_total = full_gmv_full + full_gmv_xd + full_gmv_flex + full_gmv_ds
        share_full_pct = (full_gmv_full / full_total * 100) if full_total > 0 else 0
        ct_mix["full"] += full_gmv_full
        ct_mix["xd"] += full_gmv_xd
        ct_mix["flex"] += full_gmv_flex
        ct_mix["ds"] += full_gmv_ds
        ct_gmv_perdido += full_gmv_perdido
        ct_stockout += full_stockout
        ct_doh_baixo += full_doh

        # ADS
        invest_pads = 0
        invest_bads = 0
        gmv_ads = 0
        ads_diario = []
        for r in sorted(rows_ads, key=lambda x: x["data"]):
            d = r["data"][:10]
            p = safe_float(r["invest_pads"])
            b = safe_float(r["invest_bads"])
            g = safe_float(r["gmv_ads"])
            ads_diario.append({"data": d, "pads": round(p, 2), "bads": round(b, 2)})
            if d >= str(MTD_INI):
                invest_pads += p
                invest_bads += b
                gmv_ads += g

        invest_total = invest_pads + invest_bads
        acos = (invest_total / gmv_ads * 100) if gmv_ads > 0 else 0
        ct_invest_ads += invest_total
        ct_gmv_ads += gmv_ads

        # ── GERAÇÃO DE ALERTAS ──
        if var_d7 is not None and var_d7 < -20:
            alertas.append({
                "id": sid, "nome": nome,
                "tipo": "queda_gmv", "prioridade": "alta",
                "descricao": f"GMV de ontem caiu {abs(var_d7):.0f}% vs mesmo dia semana passada",
                "valor_fmt": f"Ontem: {fmt_py(gmv_ontem)} | D-7: {fmt_py(gmv_d7)}"
            })
        elif var_d7 is not None and var_d7 < -10:
            alertas.append({
                "id": sid, "nome": nome,
                "tipo": "queda_gmv", "prioridade": "media",
                "descricao": f"GMV de ontem caiu {abs(var_d7):.0f}% vs mesmo dia semana passada",
                "valor_fmt": f"Ontem: {fmt_py(gmv_ontem)} | D-7: {fmt_py(gmv_d7)}"
            })

        if full_stockout >= 10:
            alertas.append({
                "id": sid, "nome": nome,
                "tipo": "stockout", "prioridade": "alta",
                "descricao": f"{full_stockout} SKUs em stockout hoje no Full",
                "valor_fmt": f"GMV perdido: {fmt_py(full_gmv_perdido)}"
            })
        elif full_stockout >= 3:
            alertas.append({
                "id": sid, "nome": nome,
                "tipo": "stockout", "prioridade": "media",
                "descricao": f"{full_stockout} SKUs em stockout hoje no Full",
                "valor_fmt": f"GMV perdido: {fmt_py(full_gmv_perdido)}"
            })

        if invest_total == 0 and gmv_mtd > 10000:
            alertas.append({
                "id": sid, "nome": nome,
                "tipo": "ads_parado", "prioridade": "media",
                "descricao": "Sem investimento em ADS no período",
                "valor_fmt": f"GMV MTD: {fmt_py(gmv_mtd)}"
            })

        sellers_data[str(sid)] = {
            "gmv_mtd": round(gmv_mtd, 2),
            "gmv_ly": round(gmv_ly_v, 2),
            "tsi_mtd": round(tsi_mtd),
            "ticket_medio": round(ticket, 2),
            "gmv_ontem": round(gmv_ontem, 2),
            "var_d7": round(var_d7, 1) if var_d7 is not None else None,
            "var_yoy": round(var_yoy, 1) if var_yoy is not None else None,
            "reputacao": None,  # enriquecido futuramente
            "gmv_diario": gmv_diario,
            "full": {
                "gmv_full": round(full_gmv_full, 2),
                "gmv_xd": round(full_gmv_xd, 2),
                "gmv_flex": round(full_gmv_flex, 2),
                "gmv_ds": round(full_gmv_ds, 2),
                "share_full_pct": round(share_full_pct, 1),
                "estoque_total": full_estoque,
                "stockout_skus": full_stockout,
                "doh_baixo": full_doh,
                "gmv_perdido": round(full_gmv_perdido, 2),
                "gmv_diario": full_diario,
                "itens": []  # detalhamento por item — expandir futuramente
            },
            "ads": {
                "invest_periodo": round(invest_total, 2),
                "invest_pads": round(invest_pads, 2),
                "invest_bads": round(invest_bads, 2),
                "gmv_ads": round(gmv_ads, 2),
                "acos": round(acos, 1),
                "diario": ads_diario
            }
        }

    # Rankings carteira
    rankings = sorted(
        [
            {
                "id": sid,
                "nome": SELLERS[sid],
                "nome_short": short_name(SELLERS[sid]),
                "gmv_periodo": sellers_data[str(sid)]["gmv_mtd"],
                "var_yoy": sellers_data[str(sid)]["var_yoy"],
                "tsi_periodo": sellers_data[str(sid)]["tsi_mtd"],
                "ticket_medio": sellers_data[str(sid)]["ticket_medio"],
                "gmv_ontem": sellers_data[str(sid)]["gmv_ontem"],
                "var_d7": sellers_data[str(sid)]["var_d7"],
                "reputacao": sellers_data[str(sid)]["reputacao"],
            }
            for sid in SELLERS
        ],
        key=lambda r: r["gmv_periodo"],
        reverse=True
    )

    full_rankings = sorted(
        [
            {
                "id": sid,
                "nome": SELLERS[sid],
                "nome_short": short_name(SELLERS[sid]),
                "share_full_pct": sellers_data[str(sid)]["full"]["share_full_pct"],
                "estoque_total": sellers_data[str(sid)]["full"]["estoque_total"],
                "stockout_skus": sellers_data[str(sid)]["full"]["stockout_skus"],
                "gmv_perdido": sellers_data[str(sid)]["full"]["gmv_perdido"],
                "doh_baixo": sellers_data[str(sid)]["full"]["doh_baixo"],
            }
            for sid in SELLERS
        ],
        key=lambda r: r["share_full_pct"],
        reverse=True
    )

    ads_rankings = sorted(
        [
            {
                "id": sid,
                "nome": SELLERS[sid],
                "nome_short": short_name(SELLERS[sid]),
                "invest_periodo": sellers_data[str(sid)]["ads"]["invest_periodo"],
                "acos": sellers_data[str(sid)]["ads"]["acos"],
            }
            for sid in SELLERS
            if sellers_data[str(sid)]["ads"]["invest_periodo"] > 0
        ],
        key=lambda r: r["invest_periodo"],
        reverse=True
    )

    gmv_diario_sorted = [
        {"data": d, "gmv": round(v, 2)}
        for d, v in sorted(ct_gmv_diario.items())
    ]

    gmv_total_mtd = sum(
        sellers_data[str(sid)]["gmv_mtd"] for sid in SELLERS
    )
    tsi_total_mtd = sum(
        sellers_data[str(sid)]["tsi_mtd"] for sid in SELLERS
    )
    ticket_medio_ct = gmv_total_mtd / tsi_total_mtd if tsi_total_mtd > 0 else 0
    gmv_ly_total = sum(
        sellers_data[str(sid)]["gmv_ly"] for sid in SELLERS
    )
    ct_acos = (ct_invest_ads / ct_gmv_ads * 100) if ct_gmv_ads > 0 else 0
    sellers_sem_ads = sum(
        1 for sid in SELLERS
        if sellers_data[str(sid)]["ads"]["invest_periodo"] == 0
    )

    return {
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sellers_config": sellers_config,
        "carteira": {
            "gmv_periodo": round(gmv_total_mtd, 2),
            "gmv_periodo_ly": round(gmv_ly_total, 2),
            "tsi_periodo": round(tsi_total_mtd),
            "ticket_medio": round(ticket_medio_ct, 2),
            "gmv_diario": gmv_diario_sorted,
            "mix_log": {k: round(v, 2) for k, v in ct_mix.items()},
            "rankings": rankings,
            "alertas": alertas,
            "full": {
                "gmv_full_total": round(ct_mix["full"], 2),
                "share_full_pct": round(
                    ct_mix["full"] / sum(ct_mix.values()) * 100
                    if sum(ct_mix.values()) > 0 else 0, 1
                ),
                "gmv_perdido_total": round(ct_gmv_perdido, 2),
                "stockout_skus_total": ct_stockout,
                "doh_baixo_total": ct_doh_baixo,
            },
            "full_rankings": full_rankings,
            "ads": {
                "invest_total": round(ct_invest_ads, 2),
                "gmv_ads_total": round(ct_gmv_ads, 2),
                "acos_medio": round(ct_acos, 1),
                "sellers_sem_ads": sellers_sem_ads,
            },
            "ads_rankings": ads_rankings,
        },
        "sellers": sellers_data,
    }


def fmt_py(v):
    """Formata valor monetário em Python."""
    if v >= 1e6:
        return f"R$ {v/1e6:.1f}M"
    if v >= 1e3:
        return f"R$ {v/1e3:.0f}k"
    return f"R$ {v:.0f}"


# ─────────────────────────────────────────────
# GERA HTML
# ─────────────────────────────────────────────
def gerar_html(data: dict):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "index.html")
    output_path = os.path.join(script_dir, "index.html")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = html.replace("__DASH_DATA__", data_json)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  ✅ HTML gerado: {output_path}")
    return output_path


# ─────────────────────────────────────────────
# GIT PUSH PARA GITHUB PAGES
# ─────────────────────────────────────────────
def git_push():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["git", "-C", script_dir, "add", "index.html"], check=True)
        msg = f"dash: atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        subprocess.run(["git", "-C", script_dir, "commit", "-m", msg], check=True)
        subprocess.run(["git", "-C", script_dir, "push"], check=True)
        print("  ✅ Push para GitHub Pages realizado.")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  Git push falhou: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"  Dashboard Carteira — {HOJE.strftime('%d/%m/%Y')}")
    print(f"  Sellers: {len(SELLERS)}")
    print(f"{'='*50}")

    print("\n[1/4] Buscando dados no BigQuery...")
    gmv_rows  = query_gmv_diario()
    gmv_ly    = query_gmv_ly()
    full_rows = query_full()
    ads_rows  = query_ads()

    print(f"\n       GMV rows: {len(gmv_rows)}")
    print(f"       Full rows: {len(full_rows)}")
    print(f"       ADS rows: {len(ads_rows)}")

    print("\n[2/4] Processando dados...")
    data = build_data(gmv_rows, gmv_ly, full_rows, ads_rows)

    print("\n[3/4] Gerando HTML...")
    # Recarrega o template (sem dados injetados)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "index.html")

    # Lê template ou regenera se já tiver dados injetados
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Se já foi injetado antes, restaura o placeholder
    if "__DASH_DATA__" not in content:
        import re
        content = re.sub(
            r'(<script id="dash-data" type="application/json">).*?(</script>)',
            r'\1__DASH_DATA__\2',
            content,
            flags=re.DOTALL
        )

    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    content = content.replace("__DASH_DATA__", data_json)

    with open(template_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ index.html atualizado.")

    print("\n[4/4] Publicando no GitHub Pages...")
    git_push()

    print(f"\n{'='*50}")
    print(f"  ✅ Dash gerado com sucesso!")
    print(f"  🌐 https://renanrteixeira-hue.github.io/dash-carteira-renan/")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
