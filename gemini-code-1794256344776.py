import datetime
import math
import json
import yfinance as yf
import pandas as pd

# Definición de la lista de acciones colombianas objetivo
STOCKS_CONFIG = [
    {"ticker": "ECOPETROL.CB", "nombre": "Ecopetrol", "nemotecnico": "ECOPETROL", "sector": "Petróleo y gas"},
    {"ticker": "PFBCOLOM.CB", "nombre": "Bancolombia (Pref.)", "nemotecnico": "PFBCOLOM", "sector": "Financiero"},
    {"ticker": "BICOLSEL.CB", "nombre": "Bancolombia (Ord.)", "nemotecnico": "BCOLOMBIA", "sector": "Financiero"},
    {"ticker": "ISA.CB", "nombre": "Interconexión Eléctrica", "nemotecnico": "ISA", "sector": "Servicios Públicos"},
    {"ticker": "GRUPOAVAL.CB", "nombre": "Grupo Aval", "nemotecnico": "GRUPOAVAL", "sector": "Financiero"},
    {"ticker": "GEB.CB", "nombre": "Grupo Energía Bogotá", "nemotecnico": "GEB", "sector": "Servicios Públicos"},
    {"ticker": "PFDAVVND.CB", "nombre": "Davivienda (Pref.)", "nemotecnico": "PFDAVVND", "sector": "Financiero"},
    {"ticker": "NUTRESA.CB", "nombre": "Grupo Nutresa", "nemotecnico": "NUTRESA", "sector": "Alimentos"}
]

def main():
    acciones_resultado = []
    errores = []

    print("Descargando datos bursátiles...")

    for config in STOCKS_CONFIG:
        ticker_str = config["ticker"]
        try:
            t = yf.Ticker(ticker_str)
            df = t.history(period="3y", auto_adjust=False)

            if df.empty or len(df) < 10:
                errores.append({"ticker": ticker_str, "motivo": "Histórico insuficiente o vacío"})
                continue

            # Limpieza básica
            df = df.dropna(subset=['Close'])
            
            # Últimos valores
            ultimo_row = df.iloc[-1]
            precio_actual = float(ultimo_row['Close'])
            fecha_actual_str = df.index[-1].strftime("%Y-%m-%d")

            # Variación día
            close_previo = float(df.iloc[-2]['Close']) if len(df) > 1 else precio_actual
            variacion_dia_pct = ((precio_actual / close_previo) - 1.0) * 100.0

            # Rentabilidad 1 Año (Adj Close)
            hace_1a_date = df.index[-1] - pd.DateOffset(years=1)
            df_1a = df[df.index >= hace_1a_date]
            if not df_1a.empty:
                adj_actual = float(df_1a.iloc[-1]['Adj Close'])
                adj_1a_inicio = float(df_1a.iloc[0]['Adj Close'])
                rent_1a_pct = ((adj_actual / adj_1a_inicio) - 1.0) * 100.0
            else:
                rent_1a_pct = 0.0

            # Rentabilidad Anual Promedio 3 Años (Adj Close)
            adj_primero = float(df.iloc[0]['Adj Close'])
            adj_ultimo = float(df.iloc[-1]['Adj Close'])
            dias_totales = (df.index[-1] - df.index[0]).days
            anios_totales = dias_totales / 365.25 if dias_totales > 0 else 3.0
            
            if adj_primero > 0 and anios_totales > 0:
                rent_anual_3a_pct = ((math.pow(adj_ultimo / adj_primero, 1.0 / anios_totales)) - 1.0) * 100.0
            else:
                rent_anual_3a_pct = 0.0

            # Volatilidad Anual (Rendimientos Logarítmicos del último año)
            if not df_1a.empty and len(df_1a) > 1:
                log_ret = (df_1a['Adj Close'] / df_1a['Adj Close'].shift(1)).apply(math.log).dropna()
                std_diaria = float(log_ret.std())
                volatilidad_anual_pct = std_diaria * math.sqrt(252) * 100.0
            else:
                volatilidad_anual_pct = 0.0

            # Caída Máxima en 1 año (Maximum Drawdown)
            if not df_1a.empty:
                prices_1a = df_1a['Adj Close']
                rolling_max = prices_1a.cummax()
                drawdown = (prices_1a - rolling_max) / rolling_max
                caida_maxima_1a_pct = float(drawdown.min()) * 100.0
            else:
                caida_maxima_1a_pct = 0.0

            # Rendimiento por Dividendo (últimos 365 días)
            div_df = df[df.index >= hace_1a_date]
            suma_divs = float(div_df['Dividends'].sum()) if 'Dividends' in div_df.columns else 0.0
            dividendo_rend_pct = (suma_divs / precio_actual * 100.0) if precio_actual > 0 else 0.0

            # Histórico mensual de últimos 3 años (último Close del mes)
            df_monthly = df['Close'].resample('ME').last().dropna()
            historico = []
            for date_idx, close_val in df_monthly.items():
                historico.append({
                    "mes": date_idx.strftime("%Y-%m"),
                    "cierre": round(float(close_val), 2)
                })

            acciones_resultado.append({
                "ticker": ticker_str,
                "nombre": config["nombre"],
                "nemotecnico": config["nemotecnico"],
                "sector": config["sector"],
                "moneda": "COP",
                "precio": round(precio_actual, 2),
                "fecha": fecha_actual_str,
                "variacion_dia_pct": round(variacion_dia_pct, 2),
                "rent_1a_pct": round(rent_1a_pct, 2),
                "rent_anual_3a_pct": round(rent_anual_3a_pct, 2),
                "volatilidad_anual_pct": round(volatilidad_anual_pct, 2),
                "caida_maxima_1a_pct": round(caida_maxima_1a_pct, 2),
                "dividendo_rend_pct": round(dividendo_rend_pct, 2),
                "historico": historico
            })

        except Exception as e:
            errores.append({"ticker": ticker_str, "motivo": str(e)})

    # Descargar TRM (USDCOP=X)
    trm_data = {"valor": None, "fecha": None}
    try:
        trm_ticker = yf.Ticker("USDCOP=X")
        trm_df = trm_ticker.history(period="5d")
        if not trm_df.empty:
            trm_data["valor"] = round(float(trm_df.iloc[-1]['Close']), 2)
            trm_data["fecha"] = trm_df.index[-1].strftime("%Y-%m-%d")
    except Exception:
        pass

    # Verificación de robustez
    if len(acciones_resultado) == 0:
        print("ALERTA: TODAS las acciones fallaron al descargarse. No se sobrescribirá datos.json.")
        return

    json_output = {
        "actualizado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Yahoo Finance (yfinance); rentabilidades con precio ajustado por dividendos",
        "trm": trm_data,
        "acciones": acciones_resultado,
        "errores": errores
    }

    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)

    print(f"\nProceso finalizado. Exitosas: {len(acciones_resultado)} | Errores: {len(errores)}")
    if errores:
        print("Detalle de errores:", errores)

if __name__ == "__main__":
    main()