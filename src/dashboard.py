import os
import pandas as pd
from shiny import App, ui, render, reactive
import plotly.express as px
import plotly.io as pio
from htmltools import HTML

# --- Load summary data ---
def load_summary_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "..", "data", "stock_summary.csv")
    df = pd.read_csv(file_path)

    # Clean string columns
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.strip()
    df["Ticker"] = df["Ticker"].str.upper()

    return df

# --- Build Shiny app ---
def build_shiny_app(df_summary):
    ticker_list = df_summary["Ticker"].tolist()
    default_ticker = ticker_list[0]

    app_ui = ui.page_fluid(
        ui.panel_title("📊 Stock Risk Dashboard"),
        ui.input_select("stock", "Choose a Stock", choices=ticker_list, selected=default_ticker),
        ui.output_ui("metrics_table"),
        ui.layout_columns(
            ui.output_ui("scatter_var"),
            ui.output_ui("scatter_es"),
            col_widths=[6, 6]
        )
    )

    def server(input, output, session):
        @reactive.Calc
        def selected_row():
            selected = input.stock()
            row = df_summary[df_summary["Ticker"] == selected.strip().upper()]
            return row.iloc[0] if not row.empty else None

        @output
        @render.ui
        def metrics_table():
            s = selected_row()
            if s is None:
                return "No data"

            name = s["Name"]
            ticker = s["Ticker"]
            n_companies = len(df_summary)

            avg_return = f"{s['Average_Return']:.2f}%"
            var = f"{s['VaR']:.2f}%"
            es = f"{s['ES']:.2f}%"
            r1 = int(s["Average_Return_Rank"])
            r2 = int(s["VaR_Rank"])
            r3 = int(s["ES_Rank"])

            html_content = f"""
            <hr style="margin-top: 1em; margin-bottom: 1em;" />
            <h4 style="margin-bottom: 0;">{name} ({ticker})</h4>
            <div style="margin-bottom: 0.5em;">Measures of Risk and Return*</div>
            <div style="margin-bottom: 1em;">(Rank based on {n_companies} companies)</div>

            <table class='table table-bordered table-sm' style='width:auto; font-size: 0.95em; table-layout: fixed;'>
            <colgroup>
                <col style="width: 120px;" />
                <col style="width: 60px;" />
                <col style="width: 120px;" />
                <col style="width: 60px;" />
                <col style="width: 120px;" />
                <col style="width: 60px;" />
            </colgroup>
            <thead>
                <tr>
                <th class="text-center" style="white-space: nowrap;">Avg&nbsp;Return</th>
                <th class="text-center">(Rank)</th>
                <th class="text-center">VaR</th>
                <th class="text-center">(Rank)</th>
                <th class="text-center">ES</th>
                <th class="text-center">(Rank)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                <td class="text-center">{avg_return}</td>
                <td class="text-center">{r1}</td>
                <td class="text-center">{var}</td>
                <td class="text-center">{r2}</td>
                <td class="text-center">{es}</td>
                <td class="text-center">{r3}</td>
                </tr>
            </tbody>
            </table>

            <div style="font-size: 0.85em; margin-top: 0.5em;"><em>*VaR and ES based on extreme-value modeling of tails.</em></div>
            """
            return HTML(html_content)



        def plot_to_html(fig):
            return HTML(pio.to_html(fig, full_html=False, include_plotlyjs="cdn"))

        @output
        @render.ui
        def scatter_var():
            s = selected_row()
            if s is None:
                return "No data"
            fig = px.scatter(
                df_summary,
                x="Average_Return",
                y="VaR",
                text="Ticker",
                title="Average Return vs VaR"
            )
            fig.add_scatter(
                x=[s["Average_Return"]],
                y=[s["VaR"]],
                mode="markers+text",
                name=s["Ticker"],
                marker=dict(size=12, color="red"),
                text=[s["Ticker"]],
                textposition="top center"
            )
            return plot_to_html(fig)

        @output
        @render.ui
        def scatter_es():
            s = selected_row()
            if s is None:
                return "No data"
            fig = px.scatter(
                df_summary,
                x="Average_Return",
                y="ES",
                text="Ticker",
                title="Average Return vs ES"
            )
            fig.add_scatter(
                x=[s["Average_Return"]],
                y=[s["ES"]],
                mode="markers+text",
                name=s["Ticker"],
                marker=dict(size=12, color="red"),
                text=[s["Ticker"]],
                textposition="top center"
            )
            return plot_to_html(fig)

    return App(app_ui, server)

# --- Run app ---
df_summary = load_summary_data()
app = build_shiny_app(df_summary)

if __name__ == "__main__":
    app.run()
    app.run()
