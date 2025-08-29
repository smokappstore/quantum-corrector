import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

def plot_simulation_results_plotly(results):
    """Genera visualizaciones interactivas de los resultados de la simulación con Plotly."""
    times = np.array(results['times'])
    fidelities = np.array(results['fidelities'])
    logical_error_prob = np.array(results['logical_error_prob'])
    correction_events = results['correction_events']
    
    # Crear subgráficos: dos filas, una para fidelidad y otra para error lógico
    fig = make_subplots(rows=2, cols=1,
                        subplot_titles=("Evolución de la Fidelidad con Corrección de Errores",
                                      "Probabilidad de Error Lógico en el Tiempo"),
                        shared_xaxes=True,
                        vertical_spacing=0.1)
    
    # Gráfico 1: Fidelidad
    fig.add_trace(
        go.Scatter(x=times, y=fidelities, mode='lines', name='Fidelidad',
                  line=dict(color='blue')),
        row=1, col=1
    )
    
    # Agregar líneas verticales para eventos de corrección
    correction_times = [event['time'] for event in correction_events]
    correction_success = [event['success'] for event in correction_events]
    for t, success in zip(correction_times, correction_success):
        color = 'green' if success else 'red'
        fig.add_vline(x=t, line_dash="dash", line_color=color,
                     annotation_text="Corrección" if success else "Fallo",
                     annotation_position="top", row=1, col=1)
    
    # Gráfico 2: Probabilidad de error lógico
    fig.add_trace(
        go.Scatter(x=times, y=logical_error_prob, mode='lines', name='Prob. Error Lógico',
                  line=dict(color='red')),
        row=2, col=1
    )
    
    # Actualizar diseño de los ejes
    fig.update_xaxes(title_text="Tiempo", row=2, col=1)
    fig.update_yaxes(title_text="Fidelidad", row=1, col=1)
    fig.update_yaxes(title_text="Prob. Error Lógico", row=2, col=1)
    
    # Actualizar diseño general
    fig.update_layout(
        title_text="Simulación de Corrección de Errores Cuánticos",
        showlegend=True,
        height=800,
        width=1000
    )
    
    # Mostrar gráfico interactivo
    fig.show()

# Llamar a la función con los resultados de la simulación
plot_simulation_results_plotly(results)