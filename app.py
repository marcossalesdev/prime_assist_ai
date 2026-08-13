"""
PrimeAssist AI - Entrypoint para execução via Streamlit
Redireciona para o aplicativo principal definido em streamlit_app.py.
"""
import os
import runpy

if __name__ == "__main__" or "streamlit" in globals():
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamlit_app.py")
    runpy.run_path(app_path, run_name="__main__")
