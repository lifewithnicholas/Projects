import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import os

def save_plot(fig, filename: str, folder: str = "../visuals"):
    os.makedirs(folder, exist_ok=True)
    fig_path = os.path.join(folder, filename)
    fig.savefig(fig_path)
    print(f"📊 Saved plot to {fig_path}")

def histogram(df, column: str):
    plt.figure(figsize=(8,5))
    sns.histplot(df[column], kde=True)
    plt.title(f"Histogram of {column}")
    save_plot(plt, f"{column}_hist.png")
    plt.close()

def scatter(df, x: str, y: str):
    plt.figure(figsize=(8,5))
    sns.scatterplot(data=df, x=x, y=y)
    plt.title(f"Scatter Plot: {x} vs {y}")
    save_plot(plt, f"{x}_vs_{y}_scatter.png")
    plt.close()

def interactive_scatter(df, x: str, y: str, color: str = None):
    fig = px.scatter(df, x=x, y=y, color=color, title=f"{x} vs {y}")
    fig.write_html(f"../visuals/{x}_vs_{y}_interactive.html")
    print(f"🌐 Interactive plot saved as {x}_vs_{y}_interactive.html")
