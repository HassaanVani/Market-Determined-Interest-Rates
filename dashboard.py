import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import threading
import asyncio
from engine.model import MacroModel

# Page configuration
st.set_page_config(
    page_title="Endogenous Money Simulation Engine",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom minimal styles
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #F8FAFC;
        border-bottom: 2px solid #334155;
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Macroeconomic Simulation Engine")
st.caption(
    "Decentralized Credit, Peer-to-Peer Loan Generation, and Interest Rate Discovery"
)

# Sidebar for simulation configuration
st.sidebar.markdown("### Model Configuration")

# Agent counts
n_firms = st.sidebar.slider(
    "Number of Firms", min_value=1, max_value=20, value=5, step=1
)
n_banks = st.sidebar.slider(
    "Number of Banks", min_value=1, max_value=5, value=2, step=1
)
steps = st.sidebar.slider(
    "Simulation Steps", min_value=2, max_value=50, value=15, step=1
)

# Regulatory Parameters
st.sidebar.markdown("### Regulatory Policy")
reserve_req = st.sidebar.slider(
    "Reserve Requirement Ratio", min_value=0.01, max_value=0.30, value=0.10, step=0.01
)
capital_req = st.sidebar.slider(
    "Basel Capital Ratio", min_value=0.01, max_value=0.20, value=0.08, step=0.01
)
leverage_limit = st.sidebar.slider(
    "Firm Leverage Limit", min_value=0.5, max_value=5.0, value=1.5, step=0.1
)

# Behavioral Parameters
st.sidebar.markdown("### Behavioral Settings")
control_mode = st.sidebar.checkbox("Control Group (Deterministic Rules)", value=False)
llm_model = st.sidebar.selectbox(
    "LLM Model", ["deepseek-r1:1.5b", "deepseek-r1:8b"], index=0
)
agent_sentiment = st.sidebar.selectbox(
    "Agent Sentiment Context", ["neutral", "optimistic", "pessimistic"], index=0
)
llm_temperature = st.sidebar.slider(
    "LLM Temperature", min_value=0.0, max_value=1.5, value=0.7, step=0.1
)

run_button = st.sidebar.button("Run Simulation", use_container_width=True)

# Main Dashboard view
if run_button:
    # Initialize simulation model
    model = MacroModel(
        n_firms=n_firms,
        n_banks=n_banks,
        db_path=":memory:",
        control_mode=control_mode,
        llm_model=llm_model,
        agent_sentiment=agent_sentiment,
        llm_temperature=llm_temperature,
        reserve_requirement=reserve_req,
        capital_requirement=capital_req,
        leverage_limit=leverage_limit,
    )

    # Placeholders for live updates
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    # Stat cards placeholders
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        m_supply_metric = st.empty()
    with col2:
        m_debt_metric = st.empty()
    with col3:
        m_inflation_metric = st.empty()
    with col4:
        m_rate_metric = st.empty()

    chart_container = st.empty()

    # Track historical metrics for plotting
    history = {
        "step": [0],
        "money_supply": [sum(f.current_balance for f in model.schedule.firms)],
        "outstanding_debt": [sum(f.current_debt for f in model.schedule.firms)],
        "nominal_rate": [model.nominal_rate],
        "realized_inflation": [model.realized_inflation],
        "real_interest_rate": [model.real_interest_rate],
        "exp_inflation": [model.exp_inflation],
        "exp_nominal_rate": [model.exp_nominal_rate],
        "defaults": [0.0],
        "write_offs": [0.0],
    }

    # Run loop
    for s in range(1, steps + 1):
        status_text.text(f"Executing step {s}/{steps}...")

        # Safe async step runner in background thread
        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(model.schedule.async_step())
            model.schedule.steps += 1
            model.schedule.time += 1
            loop.close()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        # Extract macro metrics
        tot_money = sum(f.current_balance for f in model.schedule.firms)
        tot_debt = sum(f.current_debt for f in model.schedule.firms)

        history["step"].append(s)
        history["money_supply"].append(tot_money)
        history["outstanding_debt"].append(tot_debt)
        history["nominal_rate"].append(model.nominal_rate)
        history["realized_inflation"].append(model.realized_inflation)
        history["real_interest_rate"].append(model.real_interest_rate)
        history["exp_inflation"].append(model.exp_inflation)
        history["exp_nominal_rate"].append(model.exp_nominal_rate)
        history["defaults"].append(model.defaults_in_step)
        history["write_offs"].append(model.write_offs_in_step)

        # Update metrics cards
        m_supply_metric.metric("Total Money Supply", f"${tot_money:.2f}")
        m_debt_metric.metric("Total Credit Debt", f"${tot_debt:.2f}")
        m_inflation_metric.metric(
            "Realized Inflation", f"{model.realized_inflation*100:.2f}%"
        )
        m_rate_metric.metric(
            "Real Interest Rate", f"{model.real_interest_rate*100:.2f}%"
        )

        progress_bar.progress(s / steps)

        # Plotting Matplotlib figures
        plt.style.use("dark_background")
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.patch.set_facecolor("#0E1117")

        for ax in axs.flat:
            ax.set_facecolor("#1E293B")
            ax.tick_params(colors="#94A3B8", labelsize=9)
            ax.xaxis.label.set_color("#94A3B8")
            ax.yaxis.label.set_color("#94A3B8")
            ax.grid(color="#334155", linestyle=":", linewidth=0.5)

        # 1. Money Supply and Credit Debt
        axs[0, 0].plot(
            history["step"],
            history["money_supply"],
            color="#6366F1",
            linewidth=2,
            label="Money Supply",
        )
        axs[0, 0].plot(
            history["step"],
            history["outstanding_debt"],
            color="#F59E0B",
            linewidth=2,
            linestyle="--",
            label="Credit Debt",
        )
        axs[0, 0].set_title(
            "Money Supply & Credit Debt",
            color="#F8FAFC",
            fontsize=11,
            fontweight="semibold",
        )
        axs[0, 0].legend(facecolor="#1E293B", edgecolor="#334155", loc="upper left")

        # 2. Interest Rates
        axs[0, 1].plot(
            history["step"],
            history["nominal_rate"],
            color="#3B82F6",
            linewidth=2,
            label="Nominal Rate",
        )
        axs[0, 1].plot(
            history["step"],
            history["real_interest_rate"],
            color="#10B981",
            linewidth=2,
            label="Real Rate",
        )
        axs[0, 1].set_title(
            "Nominal vs. Real Interest Rates",
            color="#F8FAFC",
            fontsize=11,
            fontweight="semibold",
        )
        axs[0, 1].legend(facecolor="#1E293B", edgecolor="#334155", loc="upper left")

        # 3. Inflation vs. Expectations
        axs[1, 0].plot(
            history["step"],
            history["realized_inflation"],
            color="#EF4444",
            linewidth=2,
            label="Realized Inflation",
        )
        axs[1, 0].plot(
            history["step"],
            history["exp_inflation"],
            color="#8B5CF6",
            linewidth=2,
            linestyle=":",
            label="Expected Inflation",
        )
        axs[1, 0].set_title(
            "Realized vs. Expected Inflation",
            color="#F8FAFC",
            fontsize=11,
            fontweight="semibold",
        )
        axs[1, 0].legend(facecolor="#1E293B", edgecolor="#334155", loc="upper left")

        # 4. Bank Defaults & Write-offs
        axs[1, 1].bar(
            history["step"],
            history["defaults"],
            color="#EC4899",
            alpha=0.7,
            label="Defaults Count",
        )
        ax2 = axs[1, 1].twinx()
        ax2.plot(
            history["step"],
            np.cumsum(history["write_offs"]),
            color="#14B8A6",
            linewidth=2,
            label="Cum. Write-Offs",
        )
        ax2.tick_params(colors="#94A3B8", labelsize=9)
        ax2.grid(False)
        axs[1, 1].set_title(
            "Bank Default Volume & Write-offs",
            color="#F8FAFC",
            fontsize=11,
            fontweight="semibold",
        )
        axs[1, 1].legend(facecolor="#1E293B", edgecolor="#334155", loc="upper left")
        ax2.legend(facecolor="#1E293B", edgecolor="#334155", loc="upper right")

        fig.tight_layout()
        chart_container.pyplot(fig)
        plt.close(fig)

    status_text.text("Simulation Run Completed Successfully.")
else:
    st.info(
        "Configure variables in the sidebar and press 'Run Simulation' to start the execution."
    )
