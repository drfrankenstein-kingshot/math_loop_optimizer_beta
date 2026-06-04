import streamlit as st
import numpy as np
import copy
import itertools
from simulator_engine import kingshot_multirally_sim2, TroopSide, load_hero_db

# Helper to calculate widget expedition bonus based on even-level steps
def get_widget_bonus(level):
    if level == 0:
        return 0.0
    even_level = (level // 2) * 2
    return 2.5 + (even_level / 2) * 2.5

# =========================================================================
# --- SECURITY GATEWAY ---
# =========================================================================
SECRET_PASSCODE = "Frank_BattleSimulator"

st.set_page_config(page_title="test Kingshot Tactical Optimizer", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Security Access Required")
    user_input = st.text_input("Enter Alliance Passcode:", type="password")
    
    if st.button("Unlock Optimizer"):
        if user_input == SECRET_PASSCODE:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid passcode. Access denied.")
else:
    # =========================================================================
    # --- OPTIMIZER APPLICATION (UNLOCKED) ---
    # =========================================================================
    st.title("📈 Kingshot Tactical Optimization Engine")
    st.caption("Isolate variables to calculate perfect combat compositions across continuous simulation runs.")
    
    if st.sidebar.button("Lock Application"):
        st.session_state["authenticated"] = False
        st.rerun()

    hero_db = load_hero_db()
# Generate hero lists with "None" appended as the first index option
    hero_list = ["None"] + sorted(list(hero_db.keys()))
    
    # If using the optimized version with explicit class lists, do this too:
# Master tracking lists updated with custom variants and Gen 4 targets
    infantry_heroes = ["None"] + sorted(["Eric", "Zoe", "Amadeus", "Helga", "Howard", "Alcar"])
    cavalry_heroes = ["None"] + sorted(["Gordon", "Fahd", "Chenko", "Petra", "Hilde", "Jabel", "Margot"])
    archer_heroes = ["None"] + sorted(["Jaegar", "Marlin", "Saul", "Yaenwoo", "Amane", "Quinn", "Rosa"])
    
    # Standard purple joiners setup
    joiner_pool_defaults = [h for h in hero_list if not hero_db[h].get('widget', {}).get('has_widget', True)]
    if not joiner_pool_defaults:
        joiner_pool_defaults = ["Gordon", "Fahd", "Chenko", "Yaenwoo", "Howard","Quinn","Amane"]
    
    # Standard purple joiners setup
    joiner_pool_defaults = [h for h in hero_list if not hero_db[h].get('widget', {}).get('has_widget', True)]
    if not joiner_pool_defaults:
        joiner_pool_defaults = ["Gordon", "Fahd", "Chenko", "Yaenwoo", "Howard","Quinn","Amane"]

    # =========================================================================
    # --- NEW CORE CONTROLLERS ---
    # =========================================================================
    st.markdown("### 🎯 Master Strategy Target")
    opt_side = st.radio("Step 1: Choose which battlefield perspective to optimize:", ("Garrison (Defenders)", "Attacker Waves (Rallies)"))
    
    if opt_side == "Garrison (Defenders)":
        opt_mode = st.selectbox("Step 2: Choose your optimization variable:", 
                                ["Troop Ratios (Fixed Total Count)", "Supporter Heroes (Fixed Troop Count)"])
    else:
        opt_mode = st.selectbox("Step 2: Choose your optimization variable:", 
                                ["Attacker Wave #1 Troop Ratios", "Attacker Wave #1 Supporter Heroes"])
        
    st.markdown("---")

    # Layout Split
    col_main, col_side = st.columns([2, 1])
    
    # -------------------------------------------------------------------------
    # --- SIDEBAR: GARRISON TARGET CONFIGURATION ---
    # -------------------------------------------------------------------------
    with col_side:
        st.header("🏰 Garrison Setup Base")
        st.markdown("**Garrison Base Troop Level**")
        gc1, gc2 = st.columns(2)
        g_tier = gc1.selectbox("Garrison Troop Tier", range(1, 12), index=10, key="gtier") 
        g_tg = gc2.selectbox("Garrison Troop TG Level", range(0, 6), index=5, key="gtg")       
        st.markdown("---")
        
        # Determine Troop Input Style for Garrison
        if opt_side == "Garrison (Defenders)" and "Troop Ratios" in opt_mode:
            g_total_troops = st.number_input("Total Garrison Capacity", value=2800000, step=100000)
            g_inf, g_cav, g_arc = 0, 0, 0  # Will scale completely in loop
        else:
            g_input_style = st.radio("Garrison Troop Input Style", ("Raw Counts", "Capacity + Ratios"), key="g_style")
            if g_input_style == "Raw Counts":
                g_inf = st.number_input("Garrison Infantry Count", value=1500000)
                g_cav = st.number_input("Garrison Cavalry Count", value=500000)
                g_arc = st.number_input("Garrison Archer Count", value=800000)
                g_total_troops = g_inf + g_cav + g_arc
            else:
                g_total_troops = st.number_input("Total Garrison Capacity Target", value=2800000, step=100000)
                st.markdown("**Adjust Garrison Ratios (Must equal 100%)**")
                
                # Initialize default grid dataframe
                g_df = [{"Class": "Infantry", "Ratio %": 50}, 
                        {"Class": "Cavalry", "Ratio %": 20}, 
                        {"Class": "Archer", "Ratio %": 30}]
                
                edited_g_df = st.data_editor(
                    g_df,
                    column_config={
                        "Class": st.column_config.TextColumn("Troop Class", disabled=True),
                        "Ratio %": st.column_config.NumberColumn("Ratio %", min_value=0, max_value=100, step=1, format="%d%%")
                    },
                    disabled=["Class"],
                    hide_index=True,
                    key="g_ratio_editor"
                )
                
                # Validation Math
                g_total_pct = sum(row["Ratio %"] for row in edited_g_df)
                if g_total_pct != 100:
                    st.error(f"❌ Garrison ratios sum to **{g_total_pct}%**. Adjust until it equals exactly 100%.")
                    g_valid = False
                else:
                    g_valid = True
                
                g_inf = int(g_total_troops * (edited_g_df[0]["Ratio %"] / 100.0))
                g_cav = int(g_total_troops * (edited_g_df[1]["Ratio %"] / 100.0))
                g_arc = int(g_total_troops * (edited_g_df[2]["Ratio %"] / 100.0))
        
        with st.expander("Garrison Leadership & Supplements"):
            st.markdown("### Main Leaders (3)")
            hc1, wc1 = st.columns([3, 1])
            g_lead1 = hc1.selectbox("Garrison Lead 1", hero_list, index=hero_list.index("Amadeus") if "Amadeus" in hero_list else 0, key="gl1")
            g_wid1 = wc1.number_input("Widget 1", 0, 10, 10, key="gw1")
            
            hc2, wc2 = st.columns([3, 1])
            g_lead2 = hc2.selectbox("Garrison Lead 2", hero_list, index=hero_list.index("Hilde") if "Hilde" in hero_list else 0, key="gl2")
            g_wid2 = wc2.number_input("Widget 2", 0, 10, 10, key="gw2")
            
            hc3, wc3 = st.columns([3, 1])
            g_lead3 = hc3.selectbox("Garrison Lead 3", hero_list, index=hero_list.index("Marlin") if "Marlin" in hero_list else 0, key="gl3")
            g_wid3 = wc3.number_input("Widget 3", 0, 10, 10, key="gw3")
            
            st.markdown("---")
            if opt_side == "Garrison (Defenders)" and "Supporter Heroes" in opt_mode:
                st.markdown("### Supporter Hero Optimization Pool")
                opt_hero_pool = st.multiselect("Joiner Pool Options", hero_list, default=joiner_pool_defaults)
                g_sup_heroes = [] 
            else:
                st.markdown("### Locked Supporter Heroes (4)")
                g_sup1 = st.selectbox("Supporter 1", hero_list, index=hero_list.index(joiner_pool_defaults[0]) if joiner_pool_defaults else 0, key="gs1")
                g_sup2 = st.selectbox("Supporter 2", hero_list, index=hero_list.index(joiner_pool_defaults[0]) if joiner_pool_defaults else 0, key="gs2")
                g_sup3 = st.selectbox("Supporter 3", hero_list, index=hero_list.index(joiner_pool_defaults[0]) if joiner_pool_defaults else 0, key="gs3")
                g_sup4 = st.selectbox("Supporter 4", hero_list, index=hero_list.index(joiner_pool_defaults[0]) if joiner_pool_defaults else 0, key="gs4")
                g_sup_heroes = [g_sup1, g_sup2, g_sup3, g_sup4]
            
        with st.expander("📊 Target Garrison Combat Stats"):
            g_inf_atk = st.number_input("Inf Attack %", value=850.0, key="gia")
            g_inf_def = st.number_input("Inf Defense %", value=900.0, key="gid")
            g_inf_let = st.number_input("Inf Lethality %", value=1100.0, key="gil")
            g_inf_hp  = st.number_input("Inf Health %", value=1100.0, key="gih")
            st.markdown("---")
            g_cav_atk = st.number_input("Cav Attack %", value=800.0, key="gca")
            g_cav_def = st.number_input("Cav Defense %", value=800.0, key="gcd")
            g_cav_let = st.number_input("Cav Lethality %", value=1000.0, key="gcl")
            g_cav_hp  = st.number_input("Cav Health %", value=1000.0, key="gch")
            st.markdown("---")
            g_arc_atk = st.number_input("Arc Attack %", value=850.0, key="gaa")
            g_arc_def = st.number_input("Arc Defense %", value=800.0, key="gad")
            g_arc_let = st.number_input("Arc Lethality %", value=1100.0, key="gal")
            g_arc_hp  = st.number_input("Arc Health %", value=1000.0, key="gah")

    # -------------------------------------------------------------------------
    # --- MAIN COLUMN: DYNAMIC ATTACKING RALLY WAVES ---
    # -------------------------------------------------------------------------
    with col_main:
        st.header("🚀 Attacking Rally Waves Setup")
        
        num_waves = st.number_input("Number of Incoming Attacking Waves", min_value=1, max_value=5, value=2, step=1)
        wave_tabs = st.tabs([f"🌊 Wave {i+1}" for i in range(num_waves)])
        
        wave_configs = {}
        
        for i, tab in enumerate(wave_tabs):
            with tab:
                st.subheader(f"Parameters for Rally Wave #{i+1}")
                
                w_col1, w_col2 = st.columns(2)
                with w_col1:
                    wc1, wc2 = st.columns(2)
                    w_tier = wc1.selectbox(f"Wave {i+1} Troop Tier", range(1, 12), index=9, key=f"wtier_{i}") 
                    w_tg = wc2.selectbox(f"Wave {i+1} Troop TG Level", range(0, 6), index=5, key=f"wtg_{i}")       
                    st.markdown("---")
                    
                    # If this is Wave 1 and we are optimizing Wave 1 ratios, lock troop configuration fields
                    if opt_side == "Attacker Waves (Rallies)" and opt_mode == "Attacker Wave #1 Troop Ratios" and i == 0:
                        st.info("🎯 **Troop Composition for Wave 1 is being optimized.** Ratios will loop continuously across execution.")
                        a_total_capacity = st.number_input("Rally Size Capacity Limit", value=1000000, step=50000, key=f"w_cap_{i}")
                        a_inf, a_cav, a_arc = 0, 0, 0
                    else:
                        w_input_style = st.radio(f"Wave {i+1} Troop Input Style", ("Raw Counts", "Rally Size + Ratios"), key=f"w_style_{i}")
                        if w_input_style == "Raw Counts":
                            a_inf = st.number_input("Infantry Count", value=600000, key=f"w_inf_{i}")
                            a_cav = st.number_input("Cavalry Count", value=200000, key=f"w_cav_{i}")
                            a_arc = st.number_input("Archer Count", value=200000, key=f"w_arc_{i}")
                            a_total_capacity = a_inf + a_cav + a_arc
                        else:
                            a_total_capacity = st.number_input("Rally Size Capacity Limit", value=1000000, step=50000, key=f"w_cap_{i}")
                            st.markdown(f"**Adjust Wave {i+1} Ratios (Must equal 100%)**")
                            
                            w_df = [{"Class": "Infantry", "Ratio %": 60}, 
                                    {"Class": "Cavalry", "Ratio %": 20}, 
                                    {"Class": "Archer", "Ratio %": 20}]
                            
                            edited_w_df = st.data_editor(
                                w_df,
                                column_config={
                                    "Class": st.column_config.TextColumn("Troop Class", disabled=True),
                                    "Ratio %": st.column_config.NumberColumn("Ratio %", min_value=0, max_value=100, step=1, format="%d%%")
                                },
                                disabled=["Class"],
                                hide_index=True,
                                key=f"w_ratio_editor_{i}"
                            )
                            
                            w_total_pct = sum(row["Ratio %"] for row in edited_w_df)
                            if w_total_pct != 100:
                                st.error(f"❌ Wave {i+1} ratios sum to **{w_total_pct}%**. Adjust until it equals exactly 100%.")
                                st.session_state[f"w_valid_{i}"] = False
                            else:
                                st.session_state[f"w_valid_{i}"] = True
                            
                            a_inf = int(a_total_capacity * (edited_w_df[0]["Ratio %"] / 100.0))
                            a_cav = int(a_total_capacity * (edited_w_df[1]["Ratio %"] / 100.0))
                            a_arc = int(a_total_capacity * (edited_w_df[2]["Ratio %"] / 100.0))
                    
                with w_col2:
                    st.markdown("**Main Leaders & Widgets**")
                    ahc1, awc1 = st.columns([3, 1])
                    a_l1 = ahc1.selectbox("Infantry Hero", infantry_heroes, index=0, key=f"wl1_{i}")
                    a_w1 = awc1.number_input("W1", 0, 10, 10, key=f"ww1_{i}")
                    
                    ahc2, awc2 = st.columns([3, 1])
                    a_l2 = ahc2.selectbox("Cavalry Hero", cavalry_heroes, index=0, key=f"wl2_{i}")
                    a_w2 = awc2.number_input("W2", 0, 10, 10, key=f"ww2_{i}")
                    
                    ahc3, awc3 = st.columns([3, 1])
                    a_l3 = ahc3.selectbox("Archer Hero", archer_heroes, index=0, key=f"wl3_{i}")
                    a_w3 = awc3.number_input("W3", 0, 10, 10, key=f"ww3_{i}")
                    
                    st.markdown("---")
                    if opt_side == "Attacker Waves (Rallies)" and opt_mode == "Attacker Wave #1 Supporter Heroes" and i == 0:
                        st.markdown("### Supporter Hero Optimization Pool (Wave 1)")
                        opt_hero_pool = st.multiselect("Wave 1 Joiner Options Pool", hero_list, default=joiner_pool_defaults, key="w1_pool_opt")
                        a_s1, a_s2, a_s3, a_s4 = None, None, None, None
                    else:
                        st.markdown("**Supporter Heroes (4)**")
                        sc1, sc2 = st.columns(2)
                        a_s1 = sc1.selectbox("Sup 1", hero_list, index=0, key=f"ws1_{i}")
                        a_s2 = sc2.selectbox("Sup 2", hero_list, index=0, key=f"ws2_{i}")
                        a_s3 = sc1.selectbox("Sup 3", hero_list, index=0, key=f"ws3_{i}")
                        a_s4 = sc2.selectbox("Sup 4", hero_list, index=0, key=f"ws4_{i}")

                with st.expander(f"📊 Wave {i+1} Core Combat Stats Override"):
                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                    with stat_col1:
                        a_inf_atk = st.number_input("Inf Atk %", value=1000.0, key=f"a_ia_{i}")
                        a_inf_def = st.number_input("Inf Def %", value=800.0, key=f"a_id_{i}")
                        a_inf_let = st.number_input("Inf Let %", value=1100.0, key=f"a_il_{i}")
                        a_inf_hp  = st.number_input("Inf HP %", value=900.0, key=f"a_ih_{i}")
                    with stat_col2:
                        a_cav_atk = st.number_input("Cav Atk %", value=900.0, key=f"a_ca_{i}")
                        a_cav_def = st.number_input("Cav Def %", value=750.0, key=f"a_cd_{i}")
                        a_cav_let = st.number_input("Cav Let %", value=850.0, key=f"a_cl_{i}")
                        a_cav_hp  = st.number_input("Cav HP %", value=700.0, key=f"a_ch_{i}")
                    with stat_col3:
                        a_arc_atk = st.number_input("Arc Atk %", value=900.0, key=f"a_aa_{i}")
                        a_arc_def = st.number_input("Arc Def %", value=700.0, key=f"a_ad_{i}")
                        a_arc_let = st.number_input("Arc Let %", value=1050.0, key=f"a_al_{i}")
                        a_arc_hp  = st.number_input("Arc HP %", value=800.0, key=f"a_ah_{i}")
                    
                    wave_configs[i] = {
                        "troops": [a_inf, a_cav, a_arc],
                        "capacity": a_total_capacity,
                        "tier": w_tier, "tg": w_tg,
                        "leaders": [a_l1, a_l2, a_l3],
                        "supporters": [a_s1, a_s2, a_s3, a_s4],
                        "widgets": [a_w1, a_w2, a_w3, 0, 0, 0, 0],
                        "stats": [
                            [a_inf_atk, a_inf_def, a_inf_let, a_inf_hp],
                            [a_cav_atk, a_cav_def, a_cav_let, a_cav_hp],
                            [a_arc_atk, a_arc_def, a_arc_let, a_arc_hp]
                        ]
                    }

        st.markdown("---")
        mc_runs = st.number_input("MC Iterations per Combination", min_value=10, max_value=500, value=40, step=10)

        # =========================================================================
        # --- COMPREHENSIVE MULTI-SIDE EXECUTABLE ENGINE ---
        # =========================================================================
        if st.button("🚀 Run Optimization Engine Grid Search"):
            with st.spinner("Processing Continuous Mathematical Strategy Grids..."):
                
                # Global Variable Conversions (Widget math removed, engine handles it)
                g_widgets = [g_wid1, g_wid2, g_wid3, 0, 0, 0, 0]
                g_combat_stats = [
                    [g_inf_atk, g_inf_def, g_inf_let, g_inf_hp],
                    [g_cav_atk, g_cav_def, g_cav_let, g_cav_hp],
                    [g_arc_atk, g_arc_def, g_arc_let, g_arc_hp]
                ]
                
                results_grid = []
                ratio_grid = [(i/10.0, j/10.0, (10-i-j)/10.0) for i in range(11) for j in range(11-i)]

                # Helper to construct active waves dynamically inside loops
                def build_waves(wave_1_override_troops=None, wave_1_override_heroes=None):
                    waves = []
                    for idx in range(num_waves):
                        w_data = wave_configs[idx]
                        w_combat_stats = copy.deepcopy(w_data["stats"])
                            
                        t_troops = w_data["troops"]
                        t_sups = w_data["supporters"]
                        
                        if idx == 0:
                            if wave_1_override_troops is not None: t_troops = wave_1_override_troops
                            if wave_1_override_heroes is not None: t_sups = wave_1_override_heroes
                            
                        waves.append(TroopSide(
                            troops=t_troops, stats=w_combat_stats,
                            leader_heroes=w_data["leaders"], supporter_heroes=t_sups,
                            tier=w_data["tier"], tg_level=w_data["tg"], widget_levels=w_data["widgets"]
                        ))
                    return waves

                # -----------------------------------------------------------------
                # EXECUTION LOGIC TREE
                # -----------------------------------------------------------------
                
                # --- CASE A: GARRISON TROOP COMPOSITION ---
                if opt_side == "Garrison (Defenders)" and "Troop Ratios" in opt_mode:
                    p_bar = st.progress(0)
                    for idx, r in enumerate(ratio_grid):
                        test_troops = [g_total_troops * r[0], g_total_troops * r[1], g_total_troops * r[2]]
                        g_setup = TroopSide(test_troops, g_combat_stats, [g_lead1, g_lead2, g_lead3], g_sup_heroes, g_tier, g_tg, g_widgets)
                        w_set = build_waves()
                        
                        tot_surv = sum(np.sum(kingshot_multirally_sim2(copy.deepcopy(w_set), copy.deepcopy(g_setup))[0].troops) for _ in range(mc_runs))
                        avg_surv = tot_surv / mc_runs
                        results_grid.append({"Configuration": f"Inf: {r[0]*100:.0f}% | Cav: {r[1]*100:.0f}% | Arc: {r[2]*100:.0f}%", "Avg Survivors": avg_surv, "Rate": (avg_surv / g_total_troops) * 100})
                        p_bar.progress((idx + 1) / len(ratio_grid))

                # --- CASE B: GARRISON SUPPORTER HEROES ---
                elif opt_side == "Garrison (Defenders)" and "Supporter Heroes" in opt_mode:
                    combos = list(itertools.combinations_with_replacement(opt_hero_pool, 4))
                    p_bar = st.progress(0)
                    for idx, combo in enumerate(combos):
                        g_setup = TroopSide([g_inf, g_cav, g_arc], g_combat_stats, [g_lead1, g_lead2, g_lead3], list(combo), g_tier, g_tg, g_widgets)
                        w_set = build_waves()
                        
                        tot_surv = sum(np.sum(kingshot_multirally_sim2(copy.deepcopy(w_set), copy.deepcopy(g_setup))[0].troops) for _ in range(mc_runs))
                        avg_surv = tot_surv / mc_runs
                        results_grid.append({"Configuration": f"{', '.join(combo)}", "Avg Survivors": avg_surv, "Rate": (avg_surv / max(1, g_total_troops)) * 100})
                        p_bar.progress((idx + 1) / len(combos))

                # --- CASE C: ATTACKER WAVE 1 TROOP COMPOSITION ---
                elif opt_side == "Attacker Waves (Rallies)" and "Troop Ratios" in opt_mode:
                    p_bar = st.progress(0)
                    w1_cap = wave_configs[0]["capacity"]
                    g_setup = TroopSide([g_inf, g_cav, g_arc], g_combat_stats, [g_lead1, g_lead2, g_lead3], g_sup_heroes, g_tier, g_tg, g_widgets)
                    
                    for idx, r in enumerate(ratio_grid):
                        test_w1_troops = [w1_cap * r[0], w1_cap * r[1], w1_cap * r[2]]
                        w_set = build_waves(wave_1_override_troops=test_w1_troops)
                        
                        tot_surv = sum(np.sum(kingshot_multirally_sim2(copy.deepcopy(w_set), copy.deepcopy(g_setup))[0].troops) for _ in range(mc_runs))
                        avg_surv = tot_surv / mc_runs
                        # For attacker optimization, we look to MINIMIZE garrison survival rate
                        results_grid.append({"Configuration": f"Wave 1 -> Inf: {r[0]*100:.0f}% | Cav: {r[1]*100:.0f}% | Arc: {r[2]*100:.0f}%", "Avg Survivors": avg_surv, "Rate": (avg_surv / max(1, g_total_troops)) * 100})
                        p_bar.progress((idx + 1) / len(ratio_grid))

                # --- CASE D: ATTACKER WAVE 1 SUPPORTER HEROES ---
                elif opt_side == "Attacker Waves (Rallies)" and "Supporter Heroes" in opt_mode:
                    combos = list(itertools.combinations_with_replacement(opt_hero_pool, 4))
                    p_bar = st.progress(0)
                    g_setup = TroopSide([g_inf, g_cav, g_arc], g_combat_stats, [g_lead1, g_lead2, g_lead3], g_sup_heroes, g_tier, g_tg, g_widgets)
                    
                    for idx, combo in enumerate(combos):
                        w_set = build_waves(wave_1_override_heroes=list(combo))
                        
                        tot_surv = sum(np.sum(kingshot_multirally_sim2(copy.deepcopy(w_set), copy.deepcopy(g_setup))[0].troops) for _ in range(mc_runs))
                        avg_surv = tot_surv / mc_runs
                        results_grid.append({"Configuration": f"Wave 1 -> {', '.join(combo)}", "Avg Survivors": avg_surv, "Rate": (avg_surv / max(1, g_total_troops)) * 100})
                        p_bar.progress((idx + 1) / len(combos))

                # =========================================================================
                # --- CONDITIONAL LEADERBOARD SORT DISPLAY ---
                # =========================================================================
                # Critical Strategy Distinction: Defenders want to MAXIMIZE survivors, Attackers want to MINIMIZE them
                if opt_side == "Garrison (Defenders)":
                    sorted_results = sorted(results_grid, key=lambda x: x["Avg Survivors"], reverse=True)
                    st.success(" GARRISON OPTIMIZATION COMPLETE (Sorted by Highest Defensive Survival)")
                else:
                    sorted_results = sorted(results_grid, key=lambda x: x["Avg Survivors"], reverse=False)
                    st.success("🔥 ATTACKER OPTIMIZATION COMPLETE (Sorted by Most Damage / Lowest Garrison Survival)")

                st.markdown("### 🏆 Top 5 Optimal Matrix Configurations")
                top_5 = sorted_results[:5]
                formatted_top_5 = [{"Rank": i+1, "Configuration": r["Configuration"], "Garrison Survivors (Avg)": f"{r['Avg Survivors']:,.0f}", "Garrison Survival Rate %": f"{r['Rate']:.1f}%"} for i, r in enumerate(top_5)]
                st.table(formatted_top_5)
                
                with st.expander("View Complete Simulation Leaderboard"):
                    full_formatted = [{"Rank": i+1, "Configuration": r["Configuration"], "Garrison Survivors (Avg)": f"{r['Avg Survivors']:,.0f}", "Garrison Survival Rate %": f"{r['Rate']:.1f}%"} for i, r in enumerate(sorted_results)]
                    st.dataframe(full_formatted, use_container_width=True)