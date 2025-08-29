from data_loader import load_csv
import visualizer as viz

def main():
    # Load dataset
    df = load_csv("../data/sample.csv")

    if df.empty:
        return

    # Generate visualizations
    viz.histogram(df, "sepal_length")
    viz.scatter(df, "sepal_length", "sepal_width")
    viz.interactive_scatter(df, "sepal_length", "petal_length", color="species")

if __name__ == "__main__":
    main()
