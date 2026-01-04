#!/usr/bin/env python3
"""
PCA Analysis for EDOP World Heritage Sites Matrix.

Performs dimensionality reduction and creates visualizations.

Usage:
    python scripts/pca_analysis.py
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# Output directory for plots
OUTPUT_DIR = Path(__file__).parent.parent / "docs"


def get_db_connection():
    """Create database connection from environment variables."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5435"),
        dbname=os.environ.get("PGDATABASE", "edop"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def load_matrix_data():
    """Load matrix data and site names from database."""
    conn = get_db_connection()

    # Get site names
    sites_df = pd.read_sql(
        "SELECT site_id, name_en FROM edop_wh_sites ORDER BY site_id",
        conn
    )

    # Get matrix data (exclude site_id column)
    matrix_df = pd.read_sql(
        "SELECT * FROM edop_matrix ORDER BY site_id",
        conn
    )

    conn.close()

    # Separate site_id and feature columns
    site_ids = matrix_df["site_id"].values
    feature_cols = [c for c in matrix_df.columns if c != "site_id"]
    X = matrix_df[feature_cols].values

    # Get site names in order
    site_names = sites_df.set_index("site_id").loc[site_ids, "name_en"].values

    return X, feature_cols, site_names


def run_pca_analysis(X, feature_cols, site_names):
    """Run PCA and return results."""
    # Handle missing values (replace NaN with 0 for one-hot columns, mean for numericals)
    X = np.nan_to_num(X, nan=0.0)

    # Standardize features (important for PCA with mixed scales)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Run PCA - keep all components to see variance explained
    n_components = min(X.shape[0] - 1, X.shape[1])  # max 19 for 20 samples
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_scaled)

    return pca, X_pca, X_scaled


def plot_explained_variance(pca, output_path):
    """Plot cumulative explained variance."""
    fig, ax = plt.subplots(figsize=(10, 5))

    cumulative_var = np.cumsum(pca.explained_variance_ratio_) * 100
    individual_var = pca.explained_variance_ratio_ * 100

    x = range(1, len(cumulative_var) + 1)

    # Bar chart for individual variance
    ax.bar(x, individual_var, alpha=0.6, label="Individual", color="steelblue")

    # Line for cumulative
    ax.plot(x, cumulative_var, "ro-", label="Cumulative", linewidth=2)

    # Add percentage labels on cumulative line
    for i, (xi, yi) in enumerate(zip(x, cumulative_var)):
        if i < 5:  # Label first 5 points
            ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points",
                       xytext=(0, 10), ha="center", fontsize=9)

    ax.set_xlabel("Principal Component", fontsize=12)
    ax.set_ylabel("Explained Variance (%)", fontsize=12)
    ax.set_title("PCA Explained Variance - EDOP World Heritage Sites", fontsize=14)
    ax.legend(loc="center right")
    ax.set_xticks(x)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return cumulative_var


def plot_pca_2d(X_pca, site_names, pca, output_path):
    """Plot sites in PC1-PC2 space."""
    fig, ax = plt.subplots(figsize=(14, 10))

    # Scatter plot
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], s=120, c="steelblue",
                        edgecolors="white", linewidth=1.5, alpha=0.8)

    # Add labels with smart positioning to avoid overlap
    texts = []
    for i, name in enumerate(site_names):
        # Shorten long names
        short_name = name if len(name) < 30 else name[:27] + "..."
        texts.append(ax.annotate(short_name, (X_pca[i, 0], X_pca[i, 1]),
                                fontsize=9, ha="left", va="bottom",
                                xytext=(5, 5), textcoords="offset points"))

    # Axis labels with variance explained
    var1 = pca.explained_variance_ratio_[0] * 100
    var2 = pca.explained_variance_ratio_[1] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}% variance)", fontsize=12)
    ax.set_ylabel(f"PC2 ({var2:.1f}% variance)", fontsize=12)
    ax.set_title("World Heritage Sites - Environmental Signature Space (PCA)", fontsize=14)

    # Add crosshairs at origin
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5, alpha=0.5)

    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_pca_3d(X_pca, site_names, pca, output_path):
    """Plot sites in PC1-PC2-PC3 space."""
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d")

    # Scatter plot
    ax.scatter(X_pca[:, 0], X_pca[:, 1], X_pca[:, 2], s=100, c="steelblue",
              edgecolors="white", linewidth=1, alpha=0.8)

    # Add labels
    for i, name in enumerate(site_names):
        short_name = name if len(name) < 20 else name[:17] + "..."
        ax.text(X_pca[i, 0], X_pca[i, 1], X_pca[i, 2], f"  {short_name}",
               fontsize=8, ha="left")

    # Axis labels
    var1 = pca.explained_variance_ratio_[0] * 100
    var2 = pca.explained_variance_ratio_[1] * 100
    var3 = pca.explained_variance_ratio_[2] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}%)", fontsize=10)
    ax.set_ylabel(f"PC2 ({var2:.1f}%)", fontsize=10)
    ax.set_zlabel(f"PC3 ({var3:.1f}%)", fontsize=10)
    ax.set_title("World Heritage Sites - 3D Environmental Space", fontsize=14)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def get_top_loadings(pca, feature_cols, n_components=3, n_top=10):
    """Get top features contributing to each component."""
    results = {}

    for pc_idx in range(n_components):
        loadings = pca.components_[pc_idx]
        # Get indices of top absolute loadings
        top_idx = np.argsort(np.abs(loadings))[-n_top:][::-1]

        results[f"PC{pc_idx + 1}"] = [
            (feature_cols[i], loadings[i])
            for i in top_idx
        ]

    return results


def print_results(pca, cumulative_var, top_loadings, X_pca, site_names):
    """Print analysis results to console."""
    print("\n" + "=" * 70)
    print("PCA ANALYSIS RESULTS")
    print("=" * 70)

    print("\n1. EXPLAINED VARIANCE")
    print("-" * 40)
    for i, (ind, cum) in enumerate(zip(pca.explained_variance_ratio_ * 100, cumulative_var)):
        if i < 10:
            print(f"   PC{i+1:2d}: {ind:5.1f}%  (cumulative: {cum:5.1f}%)")

    print(f"\n   Components for 80% variance: {np.argmax(cumulative_var >= 80) + 1}")
    print(f"   Components for 90% variance: {np.argmax(cumulative_var >= 90) + 1}")
    print(f"   Components for 95% variance: {np.argmax(cumulative_var >= 95) + 1}")

    print("\n2. TOP FEATURE LOADINGS")
    print("-" * 40)
    for pc, features in top_loadings.items():
        print(f"\n   {pc}:")
        for feat, loading in features[:7]:
            # Clean up feature name for display
            display_name = feat.replace("n_", "").replace("cat_", "").replace("_", " ")
            sign = "+" if loading > 0 else "-"
            print(f"      {sign} {display_name:30s} ({loading:+.3f})")

    print("\n3. SITE COORDINATES (PC1, PC2, PC3)")
    print("-" * 40)
    # Sort by PC1 to show gradient
    sorted_idx = np.argsort(X_pca[:, 0])
    for i in sorted_idx:
        name = site_names[i][:35].ljust(35)
        print(f"   {name} ({X_pca[i,0]:+6.2f}, {X_pca[i,1]:+6.2f}, {X_pca[i,2]:+6.2f})")


def main():
    print("EDOP PCA Analysis")
    print("=" * 50)

    # Load data
    print("\n1. Loading matrix data...")
    X, feature_cols, site_names = load_matrix_data()
    print(f"   Matrix shape: {X.shape[0]} sites × {X.shape[1]} features")

    # Run PCA
    print("\n2. Running PCA...")
    pca, X_pca, X_scaled = run_pca_analysis(X, feature_cols, site_names)
    print(f"   Reduced to {X_pca.shape[1]} components")

    # Get top loadings
    print("\n3. Analyzing loadings...")
    top_loadings = get_top_loadings(pca, feature_cols, n_components=3, n_top=10)

    # Create plots
    print("\n4. Generating plots...")

    var_plot_path = OUTPUT_DIR / "pca_variance.png"
    cumulative_var = plot_explained_variance(pca, var_plot_path)
    print(f"   Saved: {var_plot_path}")

    scatter_2d_path = OUTPUT_DIR / "pca_sites_2d.png"
    plot_pca_2d(X_pca, site_names, pca, scatter_2d_path)
    print(f"   Saved: {scatter_2d_path}")

    scatter_3d_path = OUTPUT_DIR / "pca_sites_3d.png"
    plot_pca_3d(X_pca, site_names, pca, scatter_3d_path)
    print(f"   Saved: {scatter_3d_path}")

    # Print detailed results
    print_results(pca, cumulative_var, top_loadings, X_pca, site_names)

    print("\n" + "=" * 70)
    print("Done! Plots saved to docs/")
    print("=" * 70)


if __name__ == "__main__":
    main()
