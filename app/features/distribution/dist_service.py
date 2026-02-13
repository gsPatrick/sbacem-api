import pandas as pd
import zipfile
import os
import io
import base64
import locale
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.config.config import UPLOAD_DIR, OUTPUT_DIR

# ======================== CONSTANTS ========================
CARMINE_RED = "#ab1a3e"
DARK_BLUE = "#2b2d5e"

# ======================== ASSET LOADER =====================
_asset_cache = {}

def load_asset_base64(asset_name):
    """Load an image from assets/ and return as data URI (cached)."""
    if asset_name in _asset_cache:
        return _asset_cache[asset_name]

    assets_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'templates', 'assets')
    # Normalize path
    assets_dir = os.path.normpath(assets_dir)
    file_path = os.path.join(assets_dir, asset_name)

    if not os.path.exists(file_path):
        # Try alternative path relative to backend/
        alt_path = os.path.join('app', 'templates', 'assets', asset_name)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            return ""

    ext = os.path.splitext(asset_name)[1].lower()
    mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}.get(ext, 'image/png')

    with open(file_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    data_uri = f"data:{mime};base64,{b64}"
    _asset_cache[asset_name] = data_uri
    return data_uri


# =================== BRAZILIAN FORMATTING ==================
def fmt_brl(value):
    """Format a number as Brazilian Real: R$ 1.234,56 (or R$ 0,0001 for small values)"""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "R$ 0,00"
    
    if 0 < abs(val) < 0.01:
        formatted = f"{val:,.4f}"
    else:
        formatted = f"{val:,.2f}"
        
    # Swap: comma->TEMP, dot->comma, TEMP->dot
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {formatted}"


def fmt_int_br(value):
    """Format an integer with Brazilian thousands separator (dot): 1.472.146"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return "0"
    formatted = f"{value:,}".replace(',', '.')
    return formatted


# ===================== SERVICE CLASS =======================
class DistributionService:

    @staticmethod
    def process_zip(zip_path, job_id, progress_callback=None):
        """Process a ZIP file (with nested ZIPs) and return a consolidated DataFrame."""
        all_dataframes = []
        errors = []

        def get_dist_type(filename):
            """Infer distribution type from filename."""
            lower = filename.lower()
            if "__per" in lower or "performance" in lower:
                return "Ao vivo"
            if "__mec" in lower or "mecanica" in lower:
                return "Mecânica"
            if "__sync" in lower:
                return "Sincronização"
            if "__dig" in lower or "digital" in lower:
                return "Digital"
            # Try to infer from suffix
            parts = lower.split('__')
            if len(parts) > 1:
                return parts[-1].split('.')[0].replace('_', ' ').title()
            return "Outros"

        def process_zip_recursive(zip_obj, parent_name="root"):
            """Recursively processes a ZipFile object."""
            all_files = zip_obj.namelist()

            for file_name in all_files:
                lower_name = file_name.lower()

                if file_name.endswith('.zip'):
                    try:
                        with zip_obj.open(file_name) as inner_data:
                            inner_bytes = io.BytesIO(inner_data.read())
                            with zipfile.ZipFile(inner_bytes) as inner_zip:
                                process_zip_recursive(inner_zip, file_name)
                    except Exception as e:
                        errors.append(f"Error processing nested zip {file_name} in {parent_name}: {str(e)}")

                elif file_name.endswith(('.xlsx', '.xls', '.csv')):
                    if "summary" in lower_name or "overview" in lower_name:
                        continue

                    dist_type = get_dist_type(file_name)

                    try:
                        with zip_obj.open(file_name) as f:
                            content = f.read()
                            if file_name.endswith('.csv'):
                                df = pd.read_csv(io.BytesIO(content))
                            else:
                                try:
                                    df = pd.read_excel(io.BytesIO(content), engine='calamine')
                                except Exception:
                                    df = pd.read_excel(io.BytesIO(content))

                            df['source_file'] = file_name
                            df['source_container'] = parent_name
                            df['type'] = dist_type
                            all_dataframes.append(df)
                    except Exception as e:
                        errors.append(f"Error reading file {file_name} in {parent_name}: {str(e)}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as main_zip:
                top_files = main_zip.namelist()
                total_top = len(top_files)

                for idx, name in enumerate(top_files):
                    if progress_callback:
                        progress_callback(idx + 1, total_top)

                    lower_name = name.lower()
                    if name.endswith('.zip'):
                        try:
                            with main_zip.open(name) as inner_data:
                                inner_bytes = io.BytesIO(inner_data.read())
                                with zipfile.ZipFile(inner_bytes) as inner_zip:
                                    process_zip_recursive(inner_zip, name)
                        except Exception as e:
                            errors.append(f"Error processing nested zip {name}: {str(e)}")
                    elif name.endswith(('.xlsx', '.xls', '.csv')):
                        if "summary" in lower_name or "overview" in lower_name:
                            continue
                        
                        dist_type = get_dist_type(name)

                        try:
                            with main_zip.open(name) as f:
                                content = f.read()
                                if name.endswith('.csv'):
                                    df = pd.read_csv(io.BytesIO(content))
                                else:
                                    try:
                                        df = pd.read_excel(io.BytesIO(content), engine='calamine')
                                    except Exception:
                                        df = pd.read_excel(io.BytesIO(content))
                                df['source_file'] = name
                                df['source_container'] = 'root'
                                df['type'] = dist_type
                                all_dataframes.append(df)
                        except Exception as e:
                            errors.append(f"Error reading file {name}: {str(e)}")

        except Exception as e:
            errors.append(f"Fatal error reading main zip: {str(e)}")
            return None, None, errors

        if not all_dataframes:
            return None, None, errors

        master_df = pd.concat(all_dataframes, ignore_index=True)
        master_df = master_df.fillna(0)

        consolidated_filename = f"consolidado_{job_id}.xlsx"
        consolidated_path = os.path.join(OUTPUT_DIR, consolidated_filename)
        master_df.to_excel(consolidated_path, index=False)

        return master_df, consolidated_filename, errors

    # =================== CHART GENERATION ==================
    @staticmethod
    def generate_charts(holder_df):
        """Generate donut and top-5 bar charts, return as base64 strings."""
        net_col = 'Net amnt' if 'Net amnt' in holder_df.columns else 'Net Amount'

        work_totals = holder_df.groupby('Title')[net_col].sum().sort_values(ascending=False)
        top_works = work_totals.head(5)
        others_val = work_totals.iloc[5:].sum() if len(work_totals) > 5 else 0

        # --- Donut Chart ---
        data_donut = top_works.copy()
        if others_val > 0:
            data_donut['Outros'] = others_val

        fig, ax = plt.subplots(figsize=(3.5, 3.5))
        colors = [CARMINE_RED, DARK_BLUE, '#555', '#777', '#999', '#BBB'][:len(data_donut)]
        wedges, texts, autotexts = ax.pie(
            data_donut, labels=data_donut.index, autopct='%1.2f%%',
            startangle=90, colors=colors, pctdistance=0.75,
            wedgeprops=dict(width=0.35, edgecolor='white')
        )
        for t in texts:
            t.set_fontsize(9)
            t.set_color('#000')
        for t in autotexts:
            t.set_fontsize(8)
            t.set_color('#fff')
        ax.set_aspect('equal')

        donut_buf = io.BytesIO()
        plt.savefig(donut_buf, format='png', bbox_inches='tight', transparent=True, dpi=150)
        plt.close('all')
        donut_buf.seek(0)
        donut_base64 = base64.b64encode(donut_buf.read()).decode('utf-8')

        # --- Top 5 Bar Chart ---
        fig, ax = plt.subplots(figsize=(4, 3))
        if not top_works.empty:
            # We want a fixed layout for 5 items. 
            # Positions: 0, 1, 2, 3, 4. 
            # Invert yaxis puts 0 at top.
            
            # Create a fixed index for 5 slots
            fixed_index = range(len(top_works))
            
            bars = ax.barh(fixed_index, top_works.values, color=CARMINE_RED, height=0.5)
            
            # Set fixed Y limits to simulate 5 slots (from -0.5 to 4.5)
            # This ensures the bars are always the same thickness and position regardless of count
            ax.set_ylim(-0.5, 4.5)
            
            ax.set_yticks(fixed_index)
            ax.set_yticklabels(top_works.index)
            
            ax.set_xlim(0, max(top_works.values) * 1.15 if max(top_works.values) > 0 else 1)
            
            for bar, v in zip(bars, top_works.values):
                ax.text(
                    bar.get_width() + max(top_works.values) * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    fmt_brl(v), va='center', fontsize=9, color='#000'
                )
            ax.invert_yaxis()
            ax.tick_params(axis='y', labelsize=8)
            ax.tick_params(axis='x', labelsize=0)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.xaxis.set_visible(False)
        else:
            ax.text(0.5, 0.5, 'Sem dados', ha='center')
            padding_top = 0.1
            ax.set_ylim(-0.5, 4.5)
            ax.axis('off')

        fig.tight_layout()
        bar_buf = io.BytesIO()
        plt.savefig(bar_buf, format='png', bbox_inches='tight', transparent=True, dpi=150)
        plt.close('all')
        bar_buf.seek(0)
        bar_base64 = base64.b64encode(bar_buf.read()).decode('utf-8')

        return donut_base64, bar_base64

    # ================ CONTEXT BUILDER =====================
    @staticmethod
    def build_template_context(holder_name, holder_df, chart_donut_b64, chart_bar_b64, zip_filename=""):
        """Build the flat context dictionary expected by the new report.html template."""
        net_col = 'Net amnt' if 'Net amnt' in holder_df.columns else 'Net Amount'
        play_col = 'Play count' if 'Play count' in holder_df.columns else 'Plays'

        # --- Basic Info ---
        ip_base = holder_df['Ip Base Number'].iloc[0] if 'Ip Base Number' in holder_df.columns else "N/A"

        # --- Pool Name ---
        pool_name = "N/A"
        if 'Distribution Pool Name' in holder_df.columns:
            pool_name = holder_df['Distribution Pool Name'].iloc[0]
        elif 'Pool' in holder_df.columns:
            pool_name = holder_df['Pool'].iloc[0]
        elif zip_filename:
            # Extract from ZIP filename (e.g. "deezer_1q2025")
            pool_name = zip_filename.replace('.zip', '').replace('_', ' ').title()

        # --- Period ---
        period_start = "N/A"
        period_end = "N/A"
        if 'Date from' in holder_df.columns:
            try:
                dates_from = pd.to_datetime(holder_df['Date from'], errors='coerce')
                dates_to = pd.to_datetime(holder_df['Date to'], errors='coerce') if 'Date to' in holder_df.columns else dates_from
                period_start = dates_from.min().strftime('%d/%m/%Y')
                period_end = dates_to.max().strftime('%d/%m/%Y')
            except Exception:
                pass

        # --- KPIs ---
        total_net = holder_df[net_col].sum() if net_col in holder_df.columns else 0
        total_plays_raw = holder_df[play_col].sum() if play_col in holder_df.columns else 0
        paid_works = holder_df['Title'].nunique() if 'Title' in holder_df.columns else 0
        total_launches = len(holder_df)

        # --- Percentual por Fonte (DYNAMIC) ---
        source_items = []
        if 'type' in holder_df.columns and total_net > 0:
            # Group by type and sum net amount
            source_groups = holder_df.groupby('type')[net_col].sum().sort_values(ascending=False)
            
            # Limit to Top 5 + Others
            top_sources = source_groups.head(5)
            others_val = source_groups.iloc[5:].sum() if len(source_groups) > 5 else 0

            # Define a color palette
            source_colors = ["#ab1a3e", "#2b2d5e", "#555555", "#777777", "#999999", "#aaaaaa"]
            
            for idx, (src_name, src_val) in enumerate(top_sources.items()):
                pct = round((src_val / total_net) * 100, 2)
                color = source_colors[idx % len(source_colors)]
                source_items.append({
                    "name": src_name,
                    "percent": str(pct).replace('.', ','),
                    "raw_percent": pct,
                    "color": color
                })
                
            if others_val > 0:
                pct = round((others_val / total_net) * 100, 2)
                source_items.append({
                    "name": "Outros",
                    "percent": str(pct).replace('.', ','),
                    "raw_percent": pct,
                    "color": "#cccccc"
                })
        else:
             pass

        # --- Detail Items (Página 2) ---
        detail_items = []
        if 'Title' in holder_df.columns and net_col in holder_df.columns:
            grouped = holder_df.groupby(['Title', 'type']).agg({
                net_col: 'sum',
                play_col: 'sum' if play_col in holder_df.columns else 'count'
            }).reset_index()

            grouped = grouped.sort_values(net_col, ascending=False)

            for _, row in grouped.iterrows():
                # Use total_net for percentage to be consistent with overall
                pct = round((row[net_col] / total_net) * 100, 2) if total_net > 0 else 0
                
                detail_items.append({
                    "title": str(row['Title']),
                    "type": str(row['type']),
                    "plays": fmt_int_br(row[play_col]) if play_col in row else "0",
                    "net_amnt": fmt_brl(row[net_col]),
                    "percent": f"{pct:.2f}".replace('.', ','),
                })

        # --- Assets (cached) ---
        logo_b64 = load_asset_base64('logo-sbacem.jpg')
        header_p2_b64 = load_asset_base64('header-page2.png')

        # --- Build flat context ---
        context = {
            "logo_base64": logo_b64,
            "full_name": str(holder_name),
            "ip_base": str(ip_base),
            "period_start": period_start,
            "period_end": period_end,
            "pool_name": str(pool_name),
            "total_net_amount": fmt_brl(total_net),
            "total_plays": fmt_int_br(total_plays_raw),
            "paid_works_count": str(paid_works),
            "total_launches": str(total_launches),
            "chart_donut_base64": chart_donut_b64,
            "chart_top5_base64": chart_bar_b64,
            "source_items": source_items,
            "header_page2_base64": header_p2_b64,
            "detail_items": detail_items,
        }

        return context

    # ================ PDF GENERATION ======================
    @staticmethod
    def create_pdf(context, template_env, output_path):
        """Render the report.html template with flat context and write PDF."""
        template = template_env.get_template('report.html')
        html_out = template.render(**context)
        HTML(string=html_out).write_pdf(output_path)
