import yaml
import pandas as pd
import pymap3d as pm
from scipy.spatial.transform import Rotation as R

def carregar_configuracao(caminho="config.yaml"):
    with open(caminho, 'r') as ficheiro:
        return yaml.safe_load(ficheiro)

def limpar_dados_robo(df, origem):
    """Junta o tempo e converte Coordenadas GPS para NED (Metros)"""
    
    # 1. Juntar os segundos e nanosegundos num só número (ex: 15.5 segundos)
    df['tempo_segundos'] = df['header.stamp.secs'] + (df['header.stamp.nsecs'] * 1e-9)
    
    # 2. Converter Latitude/Longitude/Altitude para N, E, D (Metros) usando a Origem
    # Pela descrição do professor: x = lat, y = lon, z = alt
    lat0, lon0, alt0 = origem['lat'], origem['lon'], origem['alt']
    
    # O pymap3d faz as contas todas por nós de uma só vez (Vetorizado!)
    n, e, d = pm.geodetic2ned(
        df['pose.pose.position.x'], 
        df['pose.pose.position.y'], 
        df['pose.pose.position.z'], 
        lat0, lon0, alt0
    )
    
    # Guardamos os resultados em colunas novas, super limpas
    df['N_metros'] = n
    df['E_metros'] = e
    df['D_metros'] = d
    
    return df

def carregar_csvs(config):
    dados_dos_robos = {}
    origem = config['referencia_superficie']
    
    for robo in config['robos']:
        id_robo = robo['id']
        caminho_csv = robo['ficheiro_csv']
        
        try:
            df = pd.read_csv(caminho_csv)
            # Assim que lemos, limpamos e fazemos a matemática toda!
            df = limpar_dados_robo(df, origem)
            dados_dos_robos[id_robo] = df
            tempo_inicial = df['tempo_segundos'].min()
            df['tempo_segundos'] = df['tempo_segundos'] - tempo_inicial
            print(f"✅ {id_robo}: {len(df)} linhas processadas e convertidas para NED!")
        except FileNotFoundError:
            print(f"❌ ERRO: Ficheiro '{caminho_csv}' não encontrado.")
            
    return dados_dos_robos

if __name__ == "__main__":
    cfg = carregar_configuracao()
    dados = carregar_csvs(cfg)
    
    for id_robo, dataframe in dados.items():
        print(f"\n🔍 Primeira linha do {id_robo}:")
        print(dataframe[['tempo_segundos', 'N_metros', 'E_metros']].head(1))
        