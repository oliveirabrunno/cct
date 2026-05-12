"""
ATP IQ powered by PIF - Scraper / Data Provider
Fornece insights analíticos como H2H avançado, performance de superfície, 
e eficácia sob pressão.

Como o ATP IQ não possui API pública aberta, este módulo centraliza a estrutura de busca:
1. Scraping da página de estatísticas do ATP Tour (Under Pressure, Service/Return leaders).
2. Fallback/Mock estrutural para ser adaptado assim que a fonte exata for especificada.
"""

import random
from utils.logger import get_logger
from generators.chart import generate_bar_chart, generate_radar_chart

log = get_logger(__name__)

ATP_STATS_BASE_URL = "https://www.atptour.com/en/stats"

def fetch_under_pressure_leaders() -> list[dict]:
    """Busca os líderes sob pressão (Break Points Salvos, Convertidos, Tie Breaks) do ATP IQ."""
    # Dados de exemplo focados em insights avançados.
    return [
        {"player": "Jannik Sinner", "stat": "Tie Breaks Ganhos", "value": "78%", "context": "O mais clutch do circuito nas horas decisivas."},
        {"player": "Carlos Alcaraz", "stat": "Break Points Convertidos", "value": "45%", "context": "Letal quando tem a chance de quebra."},
        {"player": "Novak Djokovic", "stat": "Break Points Salvos", "value": "68%", "context": "Historicamente inabalável sob pressão."}
    ]

def fetch_surface_performance(player_name: str, surface: str) -> dict:
    """Busca performance específica de um jogador em um piso (clay, grass, hard)."""
    return {
        "player": player_name,
        "surface": surface,
        "win_rate": f"{random.randint(65, 85)}%",
        "insight": f"Domínio absoluto nos ralis de fundo de quadra no {surface}."
    }

def fetch_h2h_insights(player_a: str, player_b: str) -> dict:
    """Busca estatísticas chave de confronto direto no formato ATP IQ."""
    return {
        "matchup": f"{player_a} vs {player_b}",
        "key_stat": "Ralis com mais de 9 trocas",
        "advantage": player_a,
        "insight": f"Em pontos longos, {player_a} domina as trocas diagonais contra {player_b}."
    }

def get_shocking_stat(player_name: str) -> dict:
    """Combina os dados acima para devolver uma estatística chocante (estilo ATP IQ) para um post."""
    pressure = fetch_under_pressure_leaders()
    for p in pressure:
        if player_name.lower() in p["player"].lower():
            # Generate a bar chart comparing top players
            labels = [p["player"] for p in pressure]
            values = [int(p["value"].replace("%", "")) for p in pressure]
            chart_path = generate_bar_chart(p["stat"], labels, values)
            return {"headline": f"{p['value']} {p['stat']}", "subtext": p['context'], "chart_path": chart_path}
            
    # Fallback caso não esteja na lista hardcoded
    surf = fetch_surface_performance(player_name, "saibro")
    
    # Generate a radar chart for the player
    categories = ["Saque", "Devolução", "Forehand", "Backhand", "Mental"]
    values = [random.uniform(7.0, 9.5) for _ in range(5)]
    chart_path = generate_radar_chart(player_name, categories, values)
    
    return {"headline": f"{surf['win_rate']} de vitórias no Saibro", "subtext": surf['insight'], "chart_path": chart_path}
