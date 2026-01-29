"""Summary plots and table generation."""

from __future__ import annotations

import logging
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import plotly.graph_objects as go

# import plotly.express as px
from ..utils import run_cmd

_LOGGER = logging.getLogger(__name__)


def process_files(
    quality_report: str,
    outdir: str,
    classification: str = None,
    mag_path: str = None,
    scmag_info: str = None,
    fastq_file: str = None,
    threads: int = 10,
) -> str:
    Path(outdir).mkdir(parents=True, exist_ok=True)
    df_quality = pd.read_csv(quality_report, sep="\t")
    selected = df_quality[
        [
            "Name",
            "Completeness",
            "Contamination",
            "Contig_N50",
            "Total_Contigs",
            "Genome_Size",
        ]
    ].copy()
    selected.columns = [
        "MAG_ID",
        "Completeness",
        "Contamination",
        "Contig_N50",
        "Total_Contigs",
        "Genome_Size",
    ]
    # TODO: scmag_info maybe None if not assigned in arguments
    df_scmag_info = (
        _parse_scMAGs_info(scmag_info) if scmag_info and Path(scmag_info).exists() else None
    )
    if df_scmag_info is not None:
        selected = pd.concat([selected, df_scmag_info], ignore_index=True)
    if classification is not None:
        df_classify = pd.read_csv(classification, sep="\t")
        merged = selected.merge(df_classify, on="MAG_ID", how="left")
    else:
        _LOGGER.info(
            "Species classification data not provided, skipping taxonomic annotation"
        )
        merged = selected

    columns = [
        "MAG_ID",
        "Completeness",
        "Contamination",
        "Contig_N50",
        "Total_Contigs",
        "Genome_Size",
        "Reference",
        "ANI",
        "Taxonomy",
        "Domain",
        "Phylum",
        "Class",
        "Order",
        "Family",
        "Genus",
        "Species",
    ]
    existing = [col for col in columns if col in merged.columns]
    merged = merged[existing]
    # merged.dtypes(
    #     columns={
    #         "MAG_ID": str,
    #         "Reference": str,
    #         "ANI": float,
    #         "Completeness": float,
    #         "Contamination": float,
    #         "Total_Contigs": int,
    #         "Genome_Size": int,
    #         "Contig_N50": int,
    #         "Taxonomy": str,
    #         "Domain": str,
    #         "Phylum": str,
    #         "Class": str,
    #         "Order": str,
    #         "Family": str,
    #         "Genus": str,
    #         "Species": str,
    #     }
    # )
    # For Total_Contigs is NaN, set to 1 if Genome_Size = Contig_N50 (for single contig MAGs)
    if "Total_Contigs" in merged.columns:
        # First, coerce to integers where possible without chained assignment
        merged.loc[:, "Total_Contigs"] = merged["Total_Contigs"].apply(
            lambda v: int(v) if pd.notna(v) else v
        )
        # For rows with NaN Total_Contigs but Genome_Size == Contig_N50, set to 1
        if "Genome_Size" in merged.columns and "Contig_N50" in merged.columns:
            mask = merged["Total_Contigs"].isna() & (
                merged["Genome_Size"] == merged["Contig_N50"]
            )
            merged.loc[mask, "Total_Contigs"] = 1
    # Rank MAGs by quality
    merged = _rank_mag_by_quality(merged)
    passed_mag_list = merged[merged["Quality_rank"] != "Low"]["MAG_ID"].tolist()
    _LOGGER.info(
        "%d MAGs passed quality filter (High or Medium quality)", len(passed_mag_list)
    )
    lowquality_mag_list = merged[merged["Quality_rank"] == "Low"]["MAG_ID"].tolist()
    _LOGGER.info("%d MAGs are low quality", len(lowquality_mag_list))
    
    # Check if we have any passed quality MAGs
    if len(passed_mag_list) == 0:
        _LOGGER.warning(
            "No high-quality or medium-quality MAGs detected. "
            "Abundance estimation will be skipped."
        )
    
    if mag_path is not None:
        # Save MAG files by quality lists separately
        (Path(outdir) / "passed_quality_mags").mkdir(exist_ok=True)
        (Path(outdir) / "low_quality_mags").mkdir(exist_ok=True)
        for mag_file in Path(mag_path).glob("*.fa"):
            mag_id = mag_file.stem
            if mag_id in passed_mag_list:
                dest = Path(outdir) / "passed_quality_mags" / mag_file.name
            elif mag_id in lowquality_mag_list:
                dest = Path(outdir) / "low_quality_mags" / mag_file.name
            else:
                continue
            run_cmd(["cp", "-L", str(mag_file), str(dest)])
        # Generate abundance profile if fastq_file is provided and we have passed MAGs
        if fastq_file is None:
            _LOGGER.warning(
                "FASTQ file not provided, skipping abundance profile generation"
            )
        elif len(passed_mag_list) == 0:
            _LOGGER.info(
                "No passed quality MAGs available, skipping abundance profile generation"
            )
        else:
            df_abundance = _run_sylph(
                Path(outdir) / "passed_quality_mags",
                fastq_file,
                threads,
                Path(outdir) / "tmp",
            )
            merged = merged.merge(df_abundance, on="MAG_ID", how="left")
            if classification is not None:
                _plot_abundance_sunburst(
                    merged,
                    Path(outdir) / "taxonomic_abundance.html",
                    abundance_column="Taxonomic_abundance(%)",
                    min_abundance=0.01,
                )
    # _plot_summary_dot(merged, Path(outdir) / "summary_dot.png")
    _generate_quality_stats_table(merged, Path(outdir) / "quality_stats.tsv")
    _plot_rank_completeness_contamination(
        merged, Path(outdir) / "rank_completeness_contamination.png"
    )
    _plot_contig_n50_violin(merged, Path(outdir) / "contig_n50_violin.png")
    # Reorder columns for summary output
    ordered_cols = [
        "MAG_ID",
        "Quality_rank",
        "Completeness",
        "Contamination",
        "Total_Contigs",
        "Genome_Size",
        "Contig_N50",
        "Reference",
        "ANI",
        "Taxonomic_abundance(%)",
        "Sequence_abundance(%)",
        "Species",
        "Genus",
        "Family",
        "Order",
        "Class",
        "Phylum",
        "Domain",
        # "Taxonomy",
    ]
    merged = merged[[col for col in ordered_cols if col in merged.columns]]
    top_rank_summary = _top_rank_mag(merged, top_n=20)
    # Replace the _ in column names with space for better readability
    merged.columns = [col.replace("_", " ") for col in merged.columns]
    top_rank_summary.columns = [
        col.replace("_", " ") for col in top_rank_summary.columns
    ]
    summary_path = Path(outdir) / "summary.tsv"
    merged.to_csv(summary_path, sep="\t", index=False)
    _LOGGER.info("Summary written to %s", summary_path)
    top_rank_path = Path(outdir) / "top_ranked_mag_summary.tsv"
    top_rank_summary.to_csv(top_rank_path, sep="\t", index=False)
    _LOGGER.info("Top ranked MAGs summary written to %s", top_rank_path)
    return str(summary_path)


def _generate_quality_stats_table(df: pd.DataFrame, output_tsv: Path) -> None:
    """Generate a 1x6 TSV with counts and genome sizes for MAG quality.

    Columns (6): High_MAGs, Medium_MAGs, All_MAGs, High_Genome_Size, Medium_Genome_Size, All_Genome_Size
    Rows (1): single content row (no index column)
    """

    required_cols = {"Quality_rank", "Genome_Size"}
    if not required_cols.issubset(df.columns):
        _LOGGER.warning(
            "Missing columns %s for quality stats table, skipping", required_cols
        )
        return

    def _safe_sum(series: pd.Series) -> float:
        return float(series.dropna().sum()) if not series.dropna().empty else 0.0

    stats = {
        "High_MAGs": len(df[df["Quality_rank"] == "High"]),
        "Medium_MAGs": len(df[df["Quality_rank"] == "Medium"]),
        "All_MAGs": len(df),
        "High_Genome_Size": _safe_sum(
            df.loc[df["Quality_rank"] == "High", "Genome_Size"]
        ),
        "Medium_Genome_Size": _safe_sum(
            df.loc[df["Quality_rank"] == "Medium", "Genome_Size"]
        ),
        "All_Genome_Size": _safe_sum(df["Genome_Size"]),
    }

    tsv_df = pd.DataFrame(
        [
            [
                stats["High_MAGs"],
                stats["Medium_MAGs"],
                stats["All_MAGs"],
                stats["High_Genome_Size"],
                stats["Medium_Genome_Size"],
                stats["All_Genome_Size"],
            ]
        ],
        columns=[
            "High_MAGs",
            "Medium_MAGs",
            "All_MAGs",
            "High_Genome_Size",
            "Medium_Genome_Size",
            "All_Genome_Size",
        ],
    )

    tsv_df.to_csv(output_tsv, sep="\t", index=False)
    _LOGGER.info("Quality stats table written to %s", output_tsv)


def _plot_rank_completeness_contamination(df: pd.DataFrame, output: Path) -> None:
    """Plot ranked Completeness and Contamination for non-low-quality MAGs.

    Completeness: y-axis, ranked descending; Contamination: x-axis, ranked ascending.
    Both rank plots are combined into a single row of subplots.
    """

    required_cols = {"Quality_rank", "Completeness", "Contamination"}
    if not required_cols.issubset(df.columns):
        _LOGGER.warning("Missing columns %s for rank plot, skipping", required_cols)
        return

    df_non_low = df[df["Quality_rank"] != "Low"].copy()
    if df_non_low.empty:
        _LOGGER.warning("No non-low-quality MAGs available for rank plot")
        return

    comp_sorted = df_non_low.sort_values("Completeness", ascending=False).reset_index(
        drop=True
    )
    comp_sorted["Rank"] = np.arange(1, len(comp_sorted) + 1)

    cont_sorted = df_non_low.sort_values("Contamination", ascending=True).reset_index(
        drop=True
    )
    cont_sorted["Rank"] = np.arange(1, len(cont_sorted) + 1)

    sns.set_style("whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=False)

    axes[0].plot(
        comp_sorted["Rank"],
        comp_sorted["Completeness"],
        marker="o",
        linestyle="-",
        color="tab:blue",
        markersize=3,
    )
    axes[0].set_xlabel("Rank (Completeness, desc)")
    axes[0].set_ylabel("Completeness (%)")
    axes[0].set_title("Completeness Rank Plot")

    axes[1].plot(
        cont_sorted["Rank"],
        cont_sorted["Contamination"],
        marker="o",
        linestyle="-",
        color="tab:red",
        markersize=3,
    )
    axes[1].set_xlabel("Rank (Contamination, asc)")
    axes[1].set_ylabel("Contamination (%)")
    axes[1].set_title("Contamination Rank Plot")

    plt.tight_layout()
    plt.savefig(output, dpi=300, bbox_inches="tight")
    plt.close()
    _LOGGER.info("Rank completeness/contamination plot saved to %s", output)


def _plot_contig_n50_violin(df: pd.DataFrame, output: Path) -> None:
    """Violin plot of Contig_N50 distribution among non-low-quality MAGs (in Mbp)."""

    required_cols = {"Quality_rank", "Contig_N50"}
    if not required_cols.issubset(df.columns):
        _LOGGER.warning(
            "Missing columns %s for Contig_N50 violin plot, skipping", required_cols
        )
        return

    df_non_low = df[df["Quality_rank"] != "Low"].copy()
    df_non_low = df_non_low.dropna(subset=["Contig_N50"])
    if df_non_low.empty:
        _LOGGER.warning("No non-low-quality MAGs with Contig_N50 for violin plot")
        return

    # Convert to Mbp
    df_non_low["Contig_N50_Mbp"] = df_non_low["Contig_N50"] / 1e6

    sns.set_style("whitegrid")
    plt.figure(figsize=(4, 4))
    sns.violinplot(y=df_non_low["Contig_N50_Mbp"], inner="box", color="skyblue")

    plt.ylabel("Contig N50 (Mbp)")
    plt.title("Contig N50 Distribution")

    # Limit plot to y >= 0
    plt.ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output, dpi=300, bbox_inches="tight")
    plt.close()
    _LOGGER.info("Contig_N50 violin plot saved to %s", output)


def _parse_scMAGs_info(scMAGs_info: str) -> pd.DataFrame:
    """Parse scMAGs info file to DataFrame."""
    df = pd.read_csv(scMAGs_info, sep="\t")
    select_columns = ["Contig", "Length", "Completeness", "Contamination"]
    df = df[select_columns].copy()
    df = df.rename(columns={"Contig": "MAG_ID", "Length": "Genome_Size"})
    # For MAGs with a single contig, N50 = genome size
    df.loc[:, "Contig_N50"] = df["Genome_Size"]
    return df


def _rank_mag_by_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Rank MAGs by quality:
    1. Completeness >=90% & contamination <=5% ranked high quality
    2. Completeness >=50% & contamination <=10% ranked medium quality
    3. quality score, defined as completeness - 5*contamination, <50 are ranked low quality
    4. Contain >2,000 contigs ranked low quality
    """

    def rank_quality(row):
        if row["Completeness"] >= 90 and row["Contamination"] <= 5:
            return "High"
        elif row["Completeness"] >= 50 and row["Contamination"] <= 10:
            return "Medium"
        elif row["Completeness"] - 5 * row["Contamination"] < 50:
            return "Low"
        elif row.get("Total_Contigs", 0) > 2000:
            return "Low"
        else:
            return "Low"

    df["Quality_rank"] = df.apply(rank_quality, axis=1)
    rank_order = {"High": 1, "Medium": 2, "Low": 3}
    df["Quality_rank_Score"] = df["Quality_rank"].map(rank_order)
    ranked_df = df.sort_values(
        by=["Quality_rank_Score", "MAG_ID"], ascending=[True, False]
    )
    ranked_df = ranked_df.drop(columns=["Quality_rank_Score"])
    return ranked_df


def _top_rank_mag(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Get top N ranked high quality MAGs by quality: completeness - 5*contamination. Only for display purpose."""
    ranked_df = df[df["Quality_rank"].isin(["High", "Medium"])].copy()
    ranked_df.loc[:, "Quality_Score"] = (
        ranked_df["Completeness"] - 5 * ranked_df["Contamination"]
    )
    ranked_df = ranked_df.sort_values(
        by=["Quality_Score", "MAG_ID"], ascending=[False, True]
    )
    ranked_df = ranked_df.drop(columns=["Quality_Score"])
    return ranked_df.head(top_n)


def _run_sylph(
    mag_path: str, fastq_file: str, threads: int, output: Path
) -> pd.DataFrame:
    """Run Sylph to generate abundance profile."""
    # Sketch database creation. create a MAG file list file for Sylph sketching, each line is a MAG fasta file path. The mag_path is a directory containing MAG fasta files.
    _LOGGER.info("Running Sylph for abundance profiling based on MAGs in %s", mag_path)
    output.mkdir(parents=True, exist_ok=True)
    if not (output / "sylph_classification.tsv").exists():
        mag_file_list = output / "mag_file_list.txt"
        with open(mag_file_list, "w") as f:
            for mag_file in Path(mag_path).glob("*.fa"):
                f.write(str(mag_file) + "\n")
        cmd = [
            "sylph",
            "sketch",
            "-l",
            str(mag_file_list),
            "-c",
            "200",
            "-t",
            str(threads),
            "-o",
            str(output / "sylph_mag_sketch"),
        ]
        run_cmd(cmd)
        cmd = [
            "sylph",
            "profile",
            str(output / "sylph_mag_sketch.syldb"),
            fastq_file,
            "-c",
            "200",
            "-t",
            str(threads),
            "-o",
            str(output / "sylph_classification.tsv"),
        ]
        run_cmd(cmd)
    abundance_df = pd.read_csv(output / "sylph_classification.tsv", sep="\t")
    abundance_df = abundance_df.rename(
        columns={
            "Genome_file": "MAG_ID",
            "Taxonomic_abundance": "Taxonomic_abundance(%)",
            "Sequence_abundance": "Sequence_abundance(%)",
        }
    )
    abundance_df.loc[:, "MAG_ID"] = abundance_df["MAG_ID"].apply(lambda x: Path(x).stem)
    return abundance_df[["MAG_ID", "Taxonomic_abundance(%)", "Sequence_abundance(%)"]]


def _plot_abundance_sunburst(
    abundance_df: pd.DataFrame,
    output_html: Path,
    abundance_column: str = "Taxonomic_abundance(%)",
    min_abundance: float = 0.01,
) -> None:
    # Define taxonomic levels in order (from outer to inner)
    tax_levels = ["Domain", "Phylum", "Class", "Order", "Family", "Genus", "Species"]
    abundance_df = abundance_df[[*tax_levels, abundance_column]].copy()
    # Deduplicate entries by summing abundances for level Species
    abundance_df = abundance_df.groupby(tax_levels, as_index=False)[
        abundance_column
    ].sum()
    # Filter out species with very low abundance
    df_filtered = abundance_df[abundance_df[abundance_column] >= min_abundance].copy()

    # Create hierarchical data structure
    sunburst_data = []

    # Create entries for each taxonomic level
    for _, row in df_filtered.iterrows():
        abundance = row[abundance_column]

        # Build hierarchical path
        path_parts = []
        for level in tax_levels:
            if (
                pd.notna(row[level])
                and row[level] != ""
                and row[level] != "NO_TAXONOMY"
            ):
                path_parts.append(row[level])
            else:
                path_parts.append(f"Unknown_{level}")

        # Create entries for each level of the hierarchy
        for i in range(len(path_parts)):
            level_name = tax_levels[i]
            current_path = " > ".join(path_parts[: i + 1])
            parent_path = " > ".join(path_parts[:i]) if i > 0 else ""

            sunburst_data.append(
                {
                    "ids": current_path,
                    "labels": path_parts[i],
                    "parents": parent_path,
                    "values": abundance,
                    "level": level_name,
                    "full_path": current_path,
                }
            )

    # Convert to DataFrame and aggregate values for each unique path
    sunburst_df = pd.DataFrame(sunburst_data)
    sunburst_df = sunburst_df.groupby(
        ["ids", "labels", "parents", "level", "full_path"], as_index=False
    )["values"].sum()

    # Sort by values for better visualization
    sunburst_df = sunburst_df.sort_values("values", ascending=False)

    # Create color mapping based on abundance values
    max_abundance = sunburst_df["values"].max()
    min_abundance = sunburst_df["values"].min()

    # Normalize values for color mapping
    if max_abundance > min_abundance:
        normalized_values = (sunburst_df["values"] - min_abundance) / (
            max_abundance - min_abundance
        )
    else:
        normalized_values = np.ones(len(sunburst_df))
    # Create the sunburst chart
    fig = go.Figure(
        go.Sunburst(
            ids=sunburst_df["ids"],
            labels=sunburst_df["labels"],
            parents=sunburst_df["parents"],
            values=sunburst_df["values"],
            branchvalues="total",
            hovertemplate="<b>%{label}</b><br>"
            + "Abundance: %{value:.3f}%<br>"
            + "Path: %{customdata}<br>"
            + "<extra></extra>",
            customdata=sunburst_df["full_path"],
            marker=dict(
                colorscale="Viridis",
                cmin=0,
                cmax=100,
                colorbar=dict(
                    title=dict(
                        text="{}".format(abundance_column.replace("_", " ").title())
                    ),
                    tickmode="linear",
                    tick0=0,
                    dtick=20,
                ),
                line=dict(color="white", width=2),
            ),
            # maxdepth=4,  # Limit depth to avoid overcrowding
            maxdepth=7,
            insidetextorientation="tangential",
        )
    )

    # Update layout
    fig.update_layout(
        title={
            "text": "Taxonomic Abundance",
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 18},
        },
        font=dict(size=12),
        width=800,
        height=800,
        margin=dict(t=100, b=50, l=50, r=50),
    )
    # Save HTML version
    fig.write_html(output_html)
    _LOGGER.info("Abundance sunburst plot saved to %s", output_html)
    return fig


# def _plot_summary_dot(df: pd.DataFrame, output: Path) -> None:
#     sns.set_style("whitegrid")
#     plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
#     plt.rcParams["axes.unicode_minus"] = False

#     group_vars = [col for col in ("Phylum", "Genus", "Species") if col in df.columns]
#     if not group_vars:
#         _LOGGER.warning("No taxonomy columns available for plotting")
#         return

#     fig, axes = plt.subplots(1, len(group_vars), figsize=(6 * len(group_vars), 5))
#     if len(group_vars) == 1:
#         axes = [axes]
#     for ax, group in zip(axes, group_vars):
#         categories = df[group].fillna("Unknown")
#         palette = sns.color_palette("tab20", n_colors=max(3, categories.nunique()))
#         scatter = ax.scatter(
#             df["Completeness"],
#             df["Contamination"],
#             c=pd.factorize(categories)[0],
#             cmap=plt.cm.get_cmap("tab20", len(palette)),
#             alpha=0.7,
#             s=60,
#         )
#         ax.set_xlabel("Completeness (%)")
#         ax.set_ylabel("Contamination (%)")
#         ax.set_title(group)
#         cbar = plt.colorbar(scatter, ax=ax)
#         cbar.set_ticks(range(categories.nunique()))
#         cbar.set_ticklabels(
#             categories.unique(), rotation=45 if categories.nunique() > 10 else 0
#         )
#         ax.grid(True, alpha=0.3)
#     plt.tight_layout()
#     plt.savefig(output, dpi=300, bbox_inches="tight")
#     plt.close()
