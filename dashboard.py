import dash
from dash import dcc, html, Input, Output, State, dash_table, callback, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import datetime
import io
import xlsxwriter
from dash.exceptions import PreventUpdate
from io import BytesIO, StringIO
import logging
import numpy as np
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== DATA LOADING ==========
def load_real_data():
    """Load data from the provided CSV file"""
    try:
        df = pd.read_csv('cleaned_web_server_logs.csv')
        logger.info("Successfully loaded data from cleaned_web_server_logs.csv")
        
        required_cols = [
            'timestamp', 'customer_id', 'session_id', 'region', 'country', 
            'product_name', 'team_name', 'transaction_amount', 'profit_made',
            'payment_method', 'transaction_status', 'response_time_ms',
            'time_spent_seconds', 'page_views'
        ]
        
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        return process_data(df)
        
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        raise

def process_data(df):
    """Process and clean the loaded data"""
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    df['month_year'] = df['timestamp'].dt.strftime('%Y-%m')
    df['year'] = df['timestamp'].dt.year
    df['profit_margin'] = (df['profit_made'] / df['transaction_amount']) * 100
    df['hour_of_day'] = df['timestamp'].dt.hour
    
    if 'team_name' in df.columns:
        df['team_name'] = df['team_name'].str.strip()
        valid_teams = ['TeamA', 'TeamB', 'TeamC']
        if not df['team_name'].isin(valid_teams + [np.nan]).all():
            logger.warning(f"Unexpected team names found: {df['team_name'].unique()}")
            df.loc[~df['team_name'].isin(valid_teams), 'team_name'] = np.nan
    
    return df

# Load the data
try:
    df = load_real_data()
except Exception as e:
    logger.error(f"Failed to load data: {str(e)}")
    df = pd.DataFrame()

# Set targets
PROFIT_TARGET = 65000000  # Updated to 65M
team_targets = {
    'TeamA': {2015: 800000, 2016: 12000000, 2017: 8000000,  2018: 1200000,2019: 10000000, 2020: 14000000, 2021: 11000000, 2022: 4000000, 2023: 2000000, 2024: 6000000, 2025: 4000000},
    'TeamB': {2015: 500000, 2016: 2500000, 2017: 2500000,  2018: 800000,2019: 2000000, 2020: 2500000, 2021: 1500000, 2022: 4000000, 2023: 2000000, 2024: 6000000, 2025: 4000000},
    'TeamC': {2015: 6000000, 2016: 5000000, 2017: 7000000, 2018: 7000000,2019: 4500000, 2020: 6000000, 2021: 7000000, 2022: 4000000, 2023: 2000000, 2024: 6000000, 2025: 4000000}
}
if 'team_name' in df.columns and 'year' in df.columns:
    df['team_target'] = df.apply(lambda row: team_targets.get(row['team_name'], {}).get(row['year'], 0), axis=1)

# Define KPI targets
REVENUE_TARGET = 100000000  # $100M
AVG_ORDER_VALUE_TARGET = 500  # $500
TRANSACTION_COUNT_TARGET = 100000  # 100,000 transactions

# ========== STYLES ==========
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "16rem",
    "padding": "0.5rem",
    "background-color": "#232F3E",
    "color": "white",
    "overflow": "hidden"
}

CONTENT_STYLE = {
    "margin-left": "8rem",
    "margin-right": "0",
    "padding": "0.5rem",
    "min-height": "100vh",
    "overflow": "hidden"  # Remove both horizontal and vertical scrolling
}

CARD_STYLE = {
    'border': 'none',
    'border-radius': '8px',
    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
    'margin-bottom': '10px',
    'background': 'white',
    'width': '100%'
}

FILTER_STYLE = {
    'border': 'none',
    'border-radius': '8px',
    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
    'margin-bottom': '10px',
    'background': 'white',
    'width': '100%',
    'max-width': '250px'
}

# Styles for KPI cards
KPI_HOME_STYLE = {
    'background-color': '#4682B4',  # Steel blue
    'border': 'none',
    'border-radius': '8px',
    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
    'margin-bottom': '10px',
    'width': '100%',
    'height': '80px',
    'padding': '0.5rem'
}

KPI_MANAGER_STYLE = {
    'background-color': 'white',  # White background for Manager page KPIs
    'border': 'none',
    'border-radius': '8px',
    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
    'margin-bottom': '10px',
    'width': '100%',
    'height': '80px',
    'padding': '0.5rem'
}

def create_kpi_card(title, value, target=None, style_type="home", show_star=False):
    # Select style based on the page
    style = KPI_HOME_STYLE if style_type == "home" else KPI_MANAGER_STYLE
    # Text color based on style type
    title_color = '#FFFFFF' if style_type == "home" else '#666666'
    value_color = '#FFFFFF' if style_type == "home" else '#232F3E'  # White for Home, dark grey for Manager

    # Determine if target is met, select triangle indicator, and calculate percentage difference
    indicator = None
    percentage_display = None
    if target is not None:
        try:
            # Handle formats like "$X.XXM", "$X.XX", or "X"
            numeric_value = float(value.replace('$', '').replace('M', 'e6').replace(',', ''))
            target_met = numeric_value >= target
            indicator_symbol = "▲" if target_met else "▼"
            indicator_color = "green" if target_met else "red"
            
            # Calculate percentage difference: ((value - target) / target) * 100
            percentage_diff = ((numeric_value - target) / target) * 100
            percentage_text = f"{percentage_diff:+.2f}%"  # Format with + or - sign, e.g., "+5.23%" or "-3.45%"
            
            indicator = html.Span(
                indicator_symbol,
                style={'color': indicator_color, 'font-size': '18px', 'margin-left': '5px', 'font-weight': 'bold'}
            )
            percentage_display = html.Span(
                percentage_text,
                style={'color': indicator_color, 'font-size': '14px', 'margin-left': '3px', 'font-weight': 'bold'}
            )
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse KPI value for comparison: {value}, error: {str(e)}")
            indicator = None
            percentage_display = None

    # Add a gold star if show_star is True
    star = None
    if show_star:
        star = html.Span(
            "★",
            style={'color': '#FFD700', 'font-size': '24px', 'margin-left': '5px', 'font-weight': 'bold'}
        )

    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(title, style={'color': title_color, 'font-size': '12px', 'margin': '0'}),
                html.Div(
                    [
                        html.H4(value, style={'color': value_color, 'font-weight': 'bold', 'font-size': '18px', 'margin': '0', 'display': 'inline'}),
                        indicator if indicator else html.Span(),
                        percentage_display if percentage_display else html.Span(),
                        star if star else html.Span(),
                    ],
                    style={'display': 'flex', 'align-items': 'center'}
                ),
            ]
        ),
        style=style
    )

def create_gauge_chart(value, title, target=100):
    return go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={'text': title, 'font': {'size': 14}},  # Increased title font size for clarity
            number={'suffix': "%", 'font': {'size': 16, 'weight': 'bold'}},  # Kept percentage bold and increased size
            gauge={
                'axis': {'range': [0, 150], 'tickwidth': 1},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 100], 'color': "red"},
                    {'range': [100, 150], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'value': value
                }
            }
        )
    ).update_layout(
        height=200,  # Increased height to accommodate all elements
        margin=dict(l=20, r=20, t=50, b=20),  # Increased top margin for the title
        title_font_size=14
    )

# ========== COMPONENTS ==========
sidebar = html.Div(
    [
        html.H2("Sales Analytics", style={'color': 'white', 'font-size': '1.5rem', 'margin-bottom': '1rem', 'text-align': 'center'}),
        html.Hr(),
        dbc.Nav(
            [
                dbc.NavLink("Home", href="/", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Sales", href="/sales", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Customer", href="/customer", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Engagement", href="/engagement", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Team A", href="/team-a", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Team B", href="/team-b", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Team C", href="/team-c", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Manager", href="/manager", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'}),
                dbc.NavLink("Stats", href="/stats", active="exact", className="nav-link-white", style={'font-size': '1rem', 'text-align': 'left', 'padding': '0.5rem'})
            ],
            vertical=True,
            pills=True
        ),
        html.Hr(),
        html.Div(
            [
                html.Small(f"Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", style={'color': '#AAAAAA', 'font-size': '0.8rem'}),
                html.Br(),
                html.Small(f"Data Range: {df['timestamp'].min().strftime('%Y-%m-%d') if not df.empty else 'N/A'} to {df['timestamp'].max().strftime('%Y-%m-%d') if not df.empty else 'N/A'}", style={'color': '#AAAAAA', 'font-size': '0.8rem'})
            ],
            className="sidebar-footer",
            style={'text-align': 'center', 'position': 'absolute', 'bottom': '1rem', 'width': '100%'}
        )
    ],
    style=SIDEBAR_STYLE
)

filter_card = dbc.Card(
    [
        dbc.CardHeader("Filters", style={'font-weight': 'bold', 'font-size': '12px'}),
        dbc.CardBody(
            [
                dcc.DatePickerRange(
                    id='date-range',
                    start_date=df['timestamp'].min() if not df.empty else datetime.datetime.now(),
                    end_date=df['timestamp'].max() if not df.empty else datetime.datetime.now(),
                    min_date_allowed=df['timestamp'].min() if not df.empty else datetime.datetime(2015,1,1),
                    max_date_allowed=df['timestamp'].max() if not df.empty else datetime.datetime(2025,12,31),
                    display_format='YYYY-MM-DD',
                    style={'width': '100%', 'margin-bottom': '8px', 'font-size': '10px'}
                ),
                dcc.Dropdown(
                    id='region-filter',
                    options=[{'label': r, 'value': r} for r in sorted(df['region'].unique())] if not df.empty else [],
                    multi=True,
                    placeholder="Select Region",
                    style={'margin-bottom': '8px', 'font-size': '10px'}
                ),
                dcc.Dropdown(
                    id='product-filter',
                    options=[{'label': p, 'value': p} for p in sorted(df['product_name'].unique())] if not df.empty else [],
                    multi=True,
                    placeholder="Select Product",
                    style={'margin-bottom': '8px', 'font-size': '10px'}
                ),
                dbc.Button("Apply Filters", id='apply-filters', color="primary", className="mr-1", style={'font-size': '10px', 'padding': '2px 5px'}),
                dbc.Button("Reset", id='reset-filters', color="secondary", style={'font-size': '10px', 'padding': '2px 5px'}),
                html.Div(id='filter-status', style={'margin-top': '8px', 'color': '#666666', 'font-size': '10px'})
            ],
            style={'padding': '0.3rem'}
        )
    ],
    style=FILTER_STYLE
)

export_card = dbc.Card(
    [
        dbc.CardHeader("Export Data", style={'font-weight': 'bold', 'font-size': '12px'}),
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("Export Excel", id='export-excel', color="success", className="w-100", style={'font-size': '10px', 'padding': '2px 5px'}),
                            width=6
                        ),
                        dbc.Col(
                            dbc.Button("Export PDF", id='export-pdf', color="danger", className="w-100", style={'font-size': '10px', 'padding': '2px 5px'}),
                            width=6
                        ),
                    ],
                    className="mb-1"
                ),
                dcc.Download(id="download-excel"),
                dcc.Download(id="download-pdf"),
                html.Div(id='export-status', style={'margin-top': '8px', 'color': '#666666', 'font-size': '10px'})
            ],
            style={'padding': '0.3rem'}
        )
    ],
    style=FILTER_STYLE
)

# ========== LAYOUTS ==========
home_layout = dbc.Container(
    [
        # Row 1: KPI Cards in a horizontal line
        dbc.Row(
            [
                dbc.Col(
                    create_kpi_card(
                        "Total Revenue",
                        f"${df['transaction_amount'].sum()/1e6:.2f}M" if not df.empty else "$0.00M",
                        target=REVENUE_TARGET,
                        style_type="home"
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Total Profit",
                        f"${df['profit_made'].sum()/1e6:.2f}M" if not df.empty else "$0.00M",
                        target=PROFIT_TARGET,
                        style_type="home"
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Avg. Order Value",
                        f"${df['transaction_amount'].mean():.2f}" if not df.empty else "$0.00",
                        target=AVG_ORDER_VALUE_TARGET,
                        style_type="home"
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Total Transactions",
                        f"{len(df):,d}" if not df.empty else "0",
                        target=TRANSACTION_COUNT_TARGET,
                        style_type="home"
                    ),
                    width=3
                )
            ],
            className="mb-2",
            style={'display': 'flex', 'flex-wrap': 'nowrap'}
        ),
        # Row 2: Filters and Export on the left, Sales by Country on the right
        dbc.Row(
            [
                # Filters and Export Column
                dbc.Col(
                    [filter_card, export_card],
                    width=2,
                    style={'padding-right': '0.5rem'}
                ),
                # Sales by Country
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Sales by Country", style={'font-weight': 'bold', 'font-size': '12px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='sales-by-country',
                                    figure=px.choropleth(
                                        df.groupby('country')['transaction_amount'].sum().reset_index() if not df.empty else pd.DataFrame({'country': [], 'transaction_amount': []}),
                                        locations='country',
                                        locationmode='country names',
                                        color='transaction_amount',
                                        hover_name='country',
                                        color_continuous_scale=px.colors.sequential.Plasma
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=5, r=5, t=20, b=5),
                                        title={'font': {'size': 12}}
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '75%'}
                    ),
                    width=10
                )
            ],
            className="mb-1"  # Reduced margin-bottom from mb-2 to mb-1 to move Row 3 up
        ),
        # Row 3: 2x2 Grid with Profit by Year and Profit Achievement
        dbc.Row(
            [
                # Profit by Year
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Profit by Year", style={'font-weight': 'bold', 'font-size': '12px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='profit-by-year',
                                    figure=px.bar(
                                        df.groupby('year')['profit_made'].sum().reset_index() if not df.empty else pd.DataFrame({'year': [], 'profit_made': []}),
                                        x='year',
                                        y='profit_made',
                                        title="Total Profit by Year"
                                    ).update_layout(
                                        height=150,
                                        margin=dict(l=5, r=5, t=20, b=5),
                                        title={'font': {'size': 12}},
                                        showlegend=False
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    width=6
                ),
                # Profit Achievement
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Profit Achievement", style={'font-weight': 'bold', 'font-size': '12px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='profit-achievement',
                                    figure=create_gauge_chart(
                                        value=(df['profit_made'].sum() / PROFIT_TARGET) * 100 if not df.empty else 0,
                                        title=f"Target: ${PROFIT_TARGET/1e6:.1f}M"
                                    )
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%', 'height': '250px', 'margin-top': '-40px'}  # Increased negative margin-top to -40px (~1 cm)
                    ),
                    width=6
                )
            ],
            className="mb-2"
        )
    ],
    fluid=True,
    style={**CONTENT_STYLE, 'padding-bottom': '0.5rem'}
)

sales_layout = dbc.Container(
    [
        html.H3("Sales Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Sales by Region", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='sales-by-region',
                                    figure=px.bar(
                                        df.groupby('region')['transaction_amount'].sum().reset_index() if not df.empty else pd.DataFrame({'region': [], 'transaction_amount': []}),
                                        x='region',
                                        y='transaction_amount',
                                        color='region',
                                        title="Total Revenue by Region"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}},
                                        showlegend=False
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Top Products", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='top-products',
                                    figure=px.treemap(
                                        df.groupby('product_name')['transaction_amount'].sum().nlargest(3).reset_index() if not df.empty else pd.DataFrame({'product_name': [], 'transaction_amount': []}),
                                        path=['product_name'],
                                        values='transaction_amount',
                                        title="Top 3 Revenue by Product"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(opacity=0.9)
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                )
            ],
            className="mb-4"
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Sales Trend", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='sales-trend',
                                    figure=px.line(
                                        df.groupby('month_year')['transaction_amount'].sum().reset_index() if not df.empty else pd.DataFrame({'month_year': [], 'transaction_amount': []}),
                                        x='month_year',
                                        y='transaction_amount',
                                        title="Monthly Revenue Trend"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(line=dict(color='#00CC96', width=3))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    width=12
                )
            ]
        )
    ],
    fluid=True,
    style=CONTENT_STYLE
)

customer_layout = dbc.Container(
    [
        html.H3("Customer Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Purchase by Age Group", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='purchase-age-group',
                                    figure=px.bar(
                                        df.groupby('age_group')['transaction_amount'].sum().reset_index() if not df.empty and 'age_group' in df.columns else pd.DataFrame({'age_group': [], 'transaction_amount': []}),
                                        x='age_group',
                                        y='transaction_amount',
                                        title="Revenue by Age Group"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}},
                                        showlegend=False
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Payment Method Preferences", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='payment-methods',
                                    figure=px.bar(
                                        df.groupby('payment_method')['transaction_amount'].sum().reset_index() if not df.empty else pd.DataFrame({'payment_method': [], 'transaction_amount': []}),
                                        x='payment_method',
                                        y='transaction_amount',
                                        title="Revenue by Payment Method"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}},
                                        showlegend=False
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                )
            ],
            className="mb-4"
        )
    ],
    fluid=True,
    style=CONTENT_STYLE
)

engagement_layout = dbc.Container(
    [
        html.H3("Engagement Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Session Duration", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='session-duration',
                                    figure=px.box(
                                        df if not df.empty else pd.DataFrame({'time_spent_seconds': []}),
                                        x='time_spent_seconds',
                                        title="Session Duration Distribution (seconds)"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=4, md=6, sm=12
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Response Times", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='response-times',
                                    figure=px.line(
                                        df.groupby('hour_of_day')['response_time_ms'].mean().reset_index() if not df.empty else pd.DataFrame({'hour_of_day': [], 'response_time_ms': []}),
                                        x='hour_of_day',
                                        y='response_time_ms',
                                        title="Average Response Time by Hour (ms)"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(line=dict(color='#00CC96', width=3))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=4, md=6, sm=12
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Page Views", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='page-views',
                                    figure=px.histogram(
                                        df if not df.empty else pd.DataFrame({'page_views': []}),
                                        x='page_views',
                                        title="Distribution of Page Views per Session"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(marker=dict(opacity=0.9))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=4, md=6, sm=12
                )
            ],
            className="mb-4"
        )
    ],
    fluid=True,
    style=CONTENT_STYLE
)

def create_team_layout(team_name):
    team_id = team_name.lower().replace(" ", "-")
    
    return dbc.Container(
        [
            html.H3(f"{team_name} Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(f"Yearly Sales (Team: {team_name})", style={'font-weight': 'bold', 'font-size': '14px'}),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id=f'{team_id}-yearly-sales',
                                        figure={}
                                    )
                                )
                            ],
                            style={**CARD_STYLE, 'width': '100%'}
                        ),
                        lg=6, md=6, sm=12
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(f"Profit Margin (Team: {team_name})", style={'font-weight': 'bold', 'font-size': '14px'}),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id=f'{team_id}-profit-margin',
                                        figure={}
                                    )
                                )
                            ],
                            style={**CARD_STYLE, 'width': '100%'}
                        ),
                        lg=6, md=6, sm=12
                    )
                ],
                className="mb-4"
            )
        ],
        fluid=True,
        style=CONTENT_STYLE
    )

# Create team layouts
team_a_layout = create_team_layout("TeamA")
team_b_layout = create_team_layout("TeamB")
team_c_layout = create_team_layout("TeamC")

manager_layout = dbc.Container(
    [
        html.H3("Manager Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
        html.Script(src="https://cdn.jsdelivr.net/npm/chart.js"),
        html.Script(id='chart-script'),
        dcc.Store(id='chart-data', data={}),
        dbc.Row(
            [
                dbc.Col(
                    create_kpi_card(
                        "Total Team Sales",
                        f"${df['transaction_amount'].sum()/1e6:.2f}M" if not df.empty else "$0.00M",
                        style_type="manager"
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Top Team",
                        df.groupby('team_name')['transaction_amount'].sum().idxmax() if not df.empty and 'team_name' in df.columns else "N/A",
                        style_type="manager",
                        show_star=True  # Add gold star to Top Team KPI
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Avg. Profit Margin",
                        f"{df['profit_margin'].mean():.1f}%" if not df.empty and 'profit_margin' in df.columns else "0.0%",
                        style_type="manager"
                    ),
                    width=3
                ),
                dbc.Col(
                    create_kpi_card(
                        "Total Transactions",
                        f"{len(df):,d}" if not df.empty else "0",
                        style_type="manager"
                    ),
                    width=3
                )
            ],
            className="mb-4"
        ),
       dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Team Sales Comparison", style={'font-weight': 'bold', 'font-size': '14px'}),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id='team-sales-comparison',
                                        figure=px.bar(
                                            df.groupby(['month_year', 'team_name'])['transaction_amount'].sum().reset_index() if not df.empty and 'team_name' in df.columns else pd.DataFrame({'month_year': [], 'team_name': [], 'transaction_amount': []}),
                                            x='month_year',
                                            y='transaction_amount',
                                            color='team_name',
                                            barmode='group',
                                            title="Monthly Sales by Team"
                                        ).update_layout(
                                            height=200,
                                            margin=dict(l=10, r=10, t=30, b=10),
                                            title={'font': {'size': 14}}
                                        ).update_traces(marker=dict(opacity=0.9))
                                    )
                                )
                            ],
                            style={**CARD_STYLE, 'width': '100%'}
                        )
                    ],
                    lg=6, md=6, sm=6  # Changed to 50% width
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Team Performance Summary", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dash_table.DataTable(
                                    id='team-summary-table',
                                    columns=[
                                        {'name': 'Team', 'id': 'team_name'},
                                        {'name': 'Total Sales', 'id': 'transaction_amount', 'type': 'numeric', 'format': {'specifier': '$.2f'}},
                                        {'name': 'Total Profit', 'id': 'profit_made', 'type': 'numeric', 'format': {'specifier': '$.2f'}},
                                        {'name': 'Transactions', 'id': 'transactions'}
                                    ],
                                    data=df.groupby('team_name').agg(
                                        transaction_amount=('transaction_amount', 'sum'),
                                        profit_made=('profit_made', 'sum'),
                                        transactions=('transaction_amount', 'count')
                                    ).reset_index().to_dict('records') if not df.empty and 'team_name' in df.columns else [],
                                    style_table={'overflowX': 'hidden', 'font-size': '12px'},
                                    style_cell={'textAlign': 'left', 'padding': '5px'},
                                    style_header={'backgroundColor': '#232F3E', 'color': 'white', 'fontWeight': 'bold', 'font-size': '12px'}
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=6  # Changed to 50% width
                )
            ]
        )
    ],
    fluid=True,
    style=CONTENT_STYLE
)

stats_layout = dbc.Container(
    [
        html.H3("Stats Dashboard", style={'color': '#232F3E', 'margin-bottom': '1rem', 'text-align': 'center'}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Monthly Visits", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='monthly-visits',
                                    figure=px.line(
                                        df.groupby('month_year')['session_id'].count().reset_index() if not df.empty else pd.DataFrame({'month_year': [], 'session_id': []}),
                                        x='month_year',
                                        y='session_id',
                                        title="Number of Visits per Month"
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(line=dict(color='#00CC96', width=3))
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Transaction Status", style={'font-weight': 'bold', 'font-size': '14px'}),
                            dbc.CardBody(
                                dcc.Graph(
                                    id='transaction-status',
                                    figure=px.pie(
                                        df.groupby('transaction_status')['session_id'].count().reset_index() if not df.empty else pd.DataFrame({'transaction_status': [], 'session_id': []}),
                                        names='transaction_status',
                                        values='session_id',
                                        title="Transaction Status Overview",
                                        hole=0.4
                                    ).update_layout(
                                        height=200,
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        title={'font': {'size': 14}}
                                    ).update_traces(opacity=0.9)
                                )
                            )
                        ],
                        style={**CARD_STYLE, 'width': '100%'}
                    ),
                    lg=6, md=6, sm=12
                )
            ],
            className="mb-4"
        )
    ],
    fluid=True,
    style=CONTENT_STYLE
)

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True,
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'}])

server = app.server

app.layout = html.Div(
    [
        dcc.Location(id="url"),
        sidebar,
        dcc.Store(id='filtered-data', data=df.to_json(date_format='iso', orient='split') if not df.empty else None),
        html.Div(id="page-content", style=CONTENT_STYLE)
    ],
    style={'height': '100vh', 'overflow': 'hidden'}
)

# ========== CALLBACKS ==========
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page_content(pathname):
    if pathname == "/":
        return home_layout
    elif pathname == "/sales":
        return sales_layout
    elif pathname == "/customer":
        return customer_layout
    elif pathname == "/engagement":
        return engagement_layout
    elif pathname == "/team-a":
        return team_a_layout
    elif pathname == "/team-b":
        return team_b_layout
    elif pathname == "/team-c":
        return team_c_layout
    elif pathname == "/manager":
        return manager_layout
    elif pathname == "/stats":
        return stats_layout
    return home_layout

@app.callback(
    [Output('filtered-data', 'data'),
     Output('filter-status', 'children')],
    [Input('apply-filters', 'n_clicks'),
     Input('reset-filters', 'n_clicks')],
    [State('date-range', 'start_date'),
     State('date-range', 'end_date'),
     State('region-filter', 'value'),
     State('product-filter', 'value')],
    prevent_initial_call=True
)
def update_store(apply_clicks, reset_clicks, start_date, end_date, regions, products):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    filtered_df = df.copy()
    message = "No filters applied"

    triggered_id = ctx.triggered[0]['prop_id']

    if triggered_id == 'reset-filters.n_clicks':
        logger.info("Filters reset")
        return df.to_json(date_format='iso', orient='split'), "Filters reset"

    applied_filters = []
    try:
        if start_date and end_date:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
            filtered_df = filtered_df[
                (filtered_df['timestamp'] >= start_date) & 
                (filtered_df['timestamp'] <= end_date)
            ]
            applied_filters.append(f"Date: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        if regions:
            filtered_df = filtered_df[filtered_df['region'].isin(regions)]
            applied_filters.append(f"Regions: {', '.join(regions)}")
        
        if products:
            filtered_df = filtered_df[filtered_df['product_name'].isin(products)]
            applied_filters.append(f"Products: {', '.join(products)}")
        
        if applied_filters:
            message = f"Filters applied: {'; '.join(applied_filters)} ({len(filtered_df)} records)"
        else:
            message = "No filters applied"

        logger.info(f"Filtered data: {len(filtered_df)} records")
        return filtered_df.to_json(date_format='iso', orient='split'), message

    except Exception as e:
        logger.error(f"Filter error: {str(e)}")
        return df.to_json(date_format='iso', orient='split'), f"Filter error: {str(e)}"

@app.callback(
    [Output('download-excel', 'data'),
     Output('export-status', 'children')],
    Input('export-excel', 'n_clicks'),
    State('filtered-data', 'data'),
    prevent_initial_call=True
)
def export_excel(n_clicks, filtered_data):
    try:
        df_export = pd.read_json(StringIO(filtered_data), orient='split')
        
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df_export.to_excel(writer, sheet_name='SalesData', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['SalesData']
        
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#232F3E',
            'font_color': 'white',
            'border': 1
        })
        
        for col_num, value in enumerate(df_export.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        for i, col in enumerate(df_export.columns):
            max_len = max(
                df_export[col].astype(str).map(len).max(),
                len(str(col))
            )
            worksheet.set_column(i, i, max_len + 1)
        
        writer.close()
        output.seek(0)
        
        return dcc.send_bytes(output.read(), filename="sales_export.xlsx"), "Excel export ready"
    except Exception as e:
        logger.error(f"Excel export error: {str(e)}")
        return None, f"Error: {str(e)}"

def generate_pdf(data):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Sales Dashboard Report")
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Sales Dashboard Report", styles['Title']))
    elements.append(Spacer(1, 12))

    filtered_df = pd.read_json(StringIO(data), orient='split')

    summary_data = [['Metric', 'Value']]
    summary_data.append(['Total Revenue', f"${filtered_df['transaction_amount'].sum():,.2f}"])
    summary_data.append(['Total Profit', f"${filtered_df['profit_made'].sum():,.2f}"])
    summary_data.append(['Average Order Value', f"${filtered_df['transaction_amount'].mean():.2f}"])
    summary_data.append(['Number of Transactions', f"{len(filtered_df):,}"])

    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#232F3E'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 24))

    charts = [
        ("Sales by Country", px.choropleth(
            filtered_df.groupby('country')['transaction_amount'].sum().reset_index(),
            locations='country',
            locationmode='country names',
            color='transaction_amount',
            hover_name='country',
            color_continuous_scale=px.colors.sequential.Plasma)),
        ("Total Revenue by Region", px.bar(
            filtered_df.groupby('region')['transaction_amount'].sum().reset_index(),
            x='region', y='transaction_amount', color='region')),
        ("Top 3 Revenue by Product", px.treemap(
            filtered_df.groupby('product_name')['transaction_amount'].sum().nlargest(3).reset_index(),
            path=['product_name'], values='transaction_amount')),
        ("Monthly Revenue Trend", px.line(
            filtered_df.groupby('month_year')['transaction_amount'].sum().reset_index(),
            x='month_year', y='transaction_amount')),
        ("Revenue by Payment Method", px.bar(
            filtered_df.groupby('payment_method')['transaction_amount'].sum().reset_index(),
            x='payment_method', y='transaction_amount')),
        ("Monthly Visits", px.line(
            filtered_df.groupby('month_year')['session_id'].count().reset_index(),
            x='month_year', y='session_id')),
        ("Transaction Status", px.pie(
            filtered_df.groupby('transaction_status')['session_id'].count().reset_index(),
            names='transaction_status', values='session_id', hole=0.4))
    ]

    for title, fig in charts:
        fig.update_layout(title={'text': title, 'font': {'size': 14}}, height=200)
        img_bytes = fig.to_image(format="png")
        img = Image(BytesIO(img_bytes), width=6 * inch, height=3 * inch)
        elements.append(Paragraph(title, styles['Heading2']))
        elements.append(img)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.callback(
    [Output('download-pdf', 'data'),
     Output('export-status', 'children', allow_duplicate=True)],
    Input('export-pdf', 'n_clicks'),
    State('filtered-data', 'data'),
    prevent_initial_call=True
)
def export_pdf(n_clicks, filtered_data):
    try:
        pdf_buffer = generate_pdf(filtered_data)
        return dcc.send_bytes(pdf_buffer.read(), filename="sales_report.pdf"), "PDF export ready"
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return None, f"Error: {str(e)}"

# Team A callback
@app.callback(
    Output('teama-yearly-sales', 'figure'),
    Output('teama-profit-margin', 'figure'),
    Input('filtered-data', 'data'),
    Input('url', 'pathname')
)
def update_team_a_visualizations(filtered_data, pathname):
    if pathname != "/team-a":
        raise PreventUpdate
        
    try:
        filtered_df = pd.read_json(StringIO(filtered_data), orient='split')
        team_df = filtered_df[filtered_df['team_name'] == "TeamA"]
        logger.info(f"TeamA DataFrame shape: {team_df.shape}")
        logger.info(f"TeamA Columns: {team_df.columns.tolist()}")

        if team_df.empty:
            logger.warning("TeamA DataFrame is empty")
            return go.Figure(), go.Figure()

        yearly_sales_data = team_df.groupby('year')['transaction_amount'].sum().reset_index()
        target_data = team_df.groupby('year')['team_target'].first().reset_index()
        
        yearly_sales = go.Figure()
        yearly_sales.add_trace(
            go.Bar(
                x=yearly_sales_data['year'],
                y=yearly_sales_data['transaction_amount'],
                name='Yearly Sales',
                marker_color='#4BC0C0',
                opacity=0.9
            )
        )
        yearly_sales.add_trace(
            go.Scatter(
                x=target_data['year'],
                y=target_data['team_target'],
                mode='lines+markers',
                name='Target',
                line=dict(color='gray', width=1),
                marker=dict(size=8),
                showlegend=True
            )
        )
        yearly_sales.update_layout(
            title='Yearly Sales for TeamA',
            xaxis_title='Year',
            yaxis_title='Transaction Amount ($)',
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title_font_size=14,
            showlegend=True
        )

        profit_margin_data = team_df.groupby('month_year')['profit_margin'].mean().reset_index()
        profit_margin = px.line(
            profit_margin_data,
            x='month_year',
            y='profit_margin',
            title="Average Profit Margin for TeamA"
        ).update_layout(
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title={'font': {'size': 14}}
        ).update_traces(line=dict(color='#00CC96', width=3))

        return yearly_sales, profit_margin

    except Exception as e:
        logger.error(f"Error updating Team A visuals: {str(e)}")
        return go.Figure(), go.Figure()

# Team B callback
@app.callback(
    Output('teamb-yearly-sales', 'figure'),
    Output('teamb-profit-margin', 'figure'),
    Input('filtered-data', 'data'),
    Input('url', 'pathname')
)
def update_team_b_visualizations(filtered_data, pathname):
    if pathname != "/team-b":
        raise PreventUpdate
        
    try:
        filtered_df = pd.read_json(StringIO(filtered_data), orient='split')
        team_df = filtered_df[filtered_df['team_name'] == "TeamB"]
        logger.info(f"TeamB DataFrame shape: {team_df.shape}")
        logger.info(f"TeamB Columns: {team_df.columns.tolist()}")

        if team_df.empty:
            logger.warning("TeamB DataFrame is empty")
            return go.Figure(), go.Figure()

        yearly_sales_data = team_df.groupby('year')['transaction_amount'].sum().reset_index()
        target_data = team_df.groupby('year')['team_target'].first().reset_index()
        
        max_sales = max(yearly_sales_data['transaction_amount'].max(), target_data['team_target'].max()) * 1.2
        yearly_sales = go.Figure()
        yearly_sales.add_trace(
            go.Bar(
                x=yearly_sales_data['year'],
                y=yearly_sales_data['transaction_amount'],
                name='Yearly Sales',
                marker_color='#26A69A',
                opacity=0.9
            )
        )
        yearly_sales.add_trace(
            go.Scatter(
                x=target_data['year'],
                y=target_data['team_target'],
                mode='lines+markers',
                name='Target',
                line=dict(color='gray', width=1),
                marker=dict(size=8),
                showlegend=True
            )
        )
        yearly_sales.update_layout(
            title='Yearly Sales for TeamB',
            xaxis_title='Year',
            yaxis_title='Transaction Amount ($)',
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title_font_size=14,
            showlegend=True,
            yaxis=dict(range=[0, max_sales])
        )

        profit_margin_data = team_df.groupby('month_year')['profit_margin'].mean().reset_index()
        profit_margin = px.line(
            profit_margin_data,
            x='month_year',
            y='profit_margin',
            title="Average Profit Margin for TeamB"
        ).update_layout(
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title={'font': {'size': 14}}
        ).update_traces(line=dict(color='#26A69A', width=3))

        return yearly_sales, profit_margin

    except Exception as e:
        logger.error(f"Error updating Team B visuals: {str(e)}")
        return go.Figure(), go.Figure()

# Team C callback
@app.callback(
    Output('teamc-yearly-sales', 'figure'),
    Output('teamc-profit-margin', 'figure'),
    Input('filtered-data', 'data'),
    Input('url', 'pathname')
)
def update_team_c_visualizations(filtered_data, pathname):
    if pathname != "/team-c":
        raise PreventUpdate
        
    try:
        filtered_df = pd.read_json(StringIO(filtered_data), orient='split')
        team_df = filtered_df[filtered_df['team_name'] == "TeamC"]
        logger.info(f"TeamC DataFrame shape: {team_df.shape}")
        logger.info(f"TeamC Columns: {team_df.columns.tolist()}")

        if team_df.empty:
            logger.warning("TeamC DataFrame is empty")
            return go.Figure(), go.Figure()

        yearly_sales_data = team_df.groupby('year')['transaction_amount'].sum().reset_index()
        target_data = team_df.groupby('year')['team_target'].first().reset_index()
        
        yearly_sales = go.Figure()
        yearly_sales.add_trace(
            go.Bar(
                x=yearly_sales_data['year'],
                y=yearly_sales_data['transaction_amount'],
                name='Yearly Sales',
                marker_color='#36A2EB',
                opacity=0.9
            )
        )
        yearly_sales.add_trace(
            go.Scatter(
                x=target_data['year'],
                y=target_data['team_target'],
                mode='lines+markers',
                name='Target',
                line=dict(color='gray', width=1),
                marker=dict(size=8),
                showlegend=True
            )
        )
        yearly_sales.update_layout(
            title='Yearly Sales for TeamC',
            xaxis_title='Year',
            yaxis_title='Transaction Amount ($)',
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title_font_size=14,
            showlegend=True
        )

        profit_margin_data = team_df.groupby('month_year')['profit_margin'].mean().reset_index()
        profit_margin = px.line(
            profit_margin_data,
            x='month_year',
            y='profit_margin',
            title="Average Profit Margin for TeamC"
        ).update_layout(
            height=200,
            margin=dict(l=10, r=10, t=30, b=10),
            title={'font': {'size': 14}}
        ).update_traces(line=dict(color='#36A2EB', width=3))

        return yearly_sales, profit_margin

    except Exception as e:
        logger.error(f"Error updating Team C visuals: {str(e)}")
        return go.Figure(), go.Figure()

# Manager View Chart.js callback
@app.callback(
    [Output('chart-data', 'data'),
     Output('chart-script', 'children')],
    Input('filtered-data', 'data'),
    Input('url', 'pathname')
)
def update_manager_charts(filtered_data, pathname):
    if pathname != "/manager":
        raise PreventUpdate

    try:
        filtered_df = pd.read_json(StringIO(filtered_data), orient='split')
        logger.info(f"Filtered DataFrame shape: {filtered_df.shape}")
        logger.info(f"Columns: {filtered_df.columns.tolist()}")

        sales_data = filtered_df.groupby(['month_year', 'team_name'])['transaction_amount'].sum().unstack(fill_value=0).reset_index()
        months = sales_data['month_year'].tolist()
        team_a_data = sales_data.get('TeamA', [0] * len(months)).tolist()
        team_b_data = sales_data.get('TeamB', [0] * len(months)).tolist()
        team_c_data = sales_data.get('TeamC', [0] * len(months)).tolist()

        chart_data = {
            'sales': {
                'months': months,
                'teamA': team_a_data,
                'teamB': team_b_data,
                'teamC': team_c_data
            }
        }

        chart_script = """
            // Destroy existing charts if they exist
            let salesChart = Chart.getChart('team-sales-comparison');
            if (salesChart) salesChart.destroy();

            new Chart(document.getElementById('team-sales-comparison'), {
                type: 'bar',
                data: {
                    labels: %s,
                    datasets: [
                        {
                            label: 'TeamA',
                            data: %s,
                            backgroundColor: '#4BC0C0',
                            barThickness: 20
                        },
                        {
                            label: 'TeamB',
                            data: %s,
                            backgroundColor: '#FF6384',
                            barThickness: 20
                        },
                        {
                            label: 'TeamC',
                            data: %s,
                            backgroundColor: '#36A2EB',
                            barThickness: 20
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Month-Year'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Transaction Amount ($)'
                            },
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Monthly Sales by Team'
                        },
                        legend: {
                            display: true
                        }
                    },
                    animation: {
                        duration: 500
                    }
                }
            });
        """ % (
            json.dumps(chart_data['sales']['months']),
            json.dumps(chart_data['sales']['teamA']),
            json.dumps(chart_data['sales']['teamB']),
            json.dumps(chart_data['sales']['teamC'])
        )

        return chart_data, chart_script

    except Exception as e:
        logger.error(f"Error updating manager charts: {str(e)}")
        return {}, ""

# Home page callbacks
@app.callback(
    [Output('sales-by-country', 'figure'),
     Output('profit-achievement', 'figure'),
     Output('profit-by-year', 'figure')],
    Input('filtered-data', 'data'),
    Input('url', 'pathname')
)
def update_home_visualizations(filtered_data, pathname):
    if pathname != "/":
        raise PreventUpdate

    if not filtered_data:
        filtered_df = df.copy()
    else:
        try:
            filtered_df = pd.read_json(StringIO(filtered_data), orient='split')
        except Exception as e:
            logger.error(f"Error loading filtered data: {str(e)}")
            filtered_df = df.copy()

    sales_by_country = px.choropleth(
        filtered_df.groupby('country')['transaction_amount'].sum().reset_index() if not filtered_df.empty else pd.DataFrame({'country': [], 'transaction_amount': []}),
        locations='country',
        locationmode='country names',
        color='transaction_amount',
        hover_name='country',
        color_continuous_scale=px.colors.sequential.Plasma
    ).update_layout(
        height=150,
        margin=dict(l=5, r=5, t=20, b=5),
        title={'text': "Sales by Country", 'font': {'size': 12}}
    ).update_traces(marker=dict(opacity=0.9))

    profit_achievement = create_gauge_chart(
        value=(filtered_df['profit_made'].sum() / PROFIT_TARGET) * 100 if not filtered_df.empty else 0,
        title=f"Target: ${PROFIT_TARGET/1e6:.1f}M"
    )

    profit_by_year = px.bar(
        filtered_df.groupby('year')['profit_made'].sum().reset_index() if not filtered_df.empty else pd.DataFrame({'year': [], 'profit_made': []}),
        x='year',
        y='profit_made',
        title="Total Profit by Year"
    ).update_layout(
        height=150,
        margin=dict(l=5, r=5, t=20, b=5),
        title={'font': {'size': 12}},
        showlegend=False
    ).update_traces(marker=dict(opacity=0.9))

    return sales_by_country, profit_achievement, profit_by_year

if __name__ == '__main__':
    app.run(debug=True)