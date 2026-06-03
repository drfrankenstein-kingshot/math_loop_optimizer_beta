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

st.set_page_config(page_title="Kingshot Garrison Optimizer", layout="wide")

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
    st.title("📈 Kingshot Garrison Optimization Engine")
    st.caption("Calculate the mathematically optimal Garrison setup against defined Attacker Waves.")
    
    if st.sidebar.button("Lock Application"):
        st.session_state["authenticated"] = False
        st.rerun()

    hero_db = load_hero_db()
    hero_list = sorted(list(hero_db.keys()))
    
    # Identify standard purple joiners automatically to set default pool
    joiner_pool_defaults = [h for h in hero_list if not hero_db[h].get('widget', {}).get('has_widget', True)]
    if not joiner_pool_defaults:
        joiner_pool_defaults = ["Gordon", "Fahd", "Chenko", "Yaenwoo", "Howard"]

    # Layout Split
    col_main, col_side = st.columns([2, 1])
    
    # -------------------------------------------------------------------------
    # --- SIDEBAR: OPTIMIZATION TARGET & GARRISON BASE ---
    # -------------------------------------------------------------------------
    with col_side:
        st.header("Optimization Target")
        
        opt_mode = st.radio(
            "Select the variable you want to optimize:",
            ("Troop Ratios (Fixed Total Count)", "Supporter Heroes (Fixed Troop Count)")
        )
        st.markdown("---")
        
        st.header("Garrison Setup Base")
        st.markdown("**Garrison Base Troop Level**")
        gc1, gc2 = st.columns(2)
        g_tier = gc1.selectbox("Garrison Troop Tier", range(1, 12), index=10, key="gtier") 
        g_tg = gc2.selectbox("Garrison Troop TG Level", range(0, 6), index=5, key="gtg")       
        st.markdown("---")
        
        # Dynamic inputs based on optimization mode
        if opt_mode == "Troop Ratios (Fixed Total Count)":
            g_total_troops = st.number_input("Total Garrison Capacity", value=2800000, step=100000)
            g_inf, g_cav, g_arc = 0, 0, 0 # Will be overridden in loop
        else:
            g_inf = st.number_input("Garrison Infantry Count", value=1500000)
            g_cav = st.number_input("Garrison Cavalry Count", value=500000)
            g_arc = st.number_input("Garrison Archer Count", value=800000)
            g_total_troops = g_inf + g_cav + g_arc
        
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
            if opt_mode == "Supporter Heroes (Fixed Troop Count)":
                st.markdown("### Supporter Hero Optimization Pool")
                st.caption("Select the pool of heroes the engine will generate combinations from.")
                opt_hero_pool = st.multiselect("Joiner Pool", hero_list, default=joiner_pool_defaults)
                g_sup_heroes = [] # Will be overridden in loop
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
        st.header("Attacking Rally Waves (The Threat)")
        
        num_waves = st.number_input("Number of Rally Waves", min_value=1, max_value=5, value=2, step=1)
        wave_tabs = st.tabs([f"🌊 Wave {i+1}" for i in range(num_waves)])
        
        wave_configs = {}
        
        for i, tab in enumerate(wave_tabs):
            with tab:
                w_col1, w_col2 = st.columns(2)
                with w_col1:
                    wc1, wc2 = st.columns(2)
                    w_tier = wc1.selectbox(f"Wave {i+1} Troop Tier", range(1, 12), index=9, key=f"wtier_{i}") 
                    w_tg = wc2.selectbox(f"Wave {i+1} Troop TG Level", range(0, 6), index=5, key=f"wtg_{i}")       
                    
                    st.markdown("**Troop Configuration**")
                    a_inf = st.number_input("Infantry Count", value=600000, key=f"w_inf_{i}")
                    a_cav = st.number_input("Cavalry Count", value=200000, key=f"w_cav_{i}")
                    a_arc = st.number_input("Archer Count", value=200000, key=f"w_arc_{i}")
                    
with w_col2:
                    st.markdown("**Main Leaders & Widgets**")
                    ahc1, awc1 = st.columns([3, 1])
                    a_l1 = ahc1.selectbox("Rally Leader 1", hero_list, index=0, key=f"wl1_{i}")
                    a_w1 = awc1.number_input("W1", 0, 10, 10, key=f"ww1_{i}")
                    
                    ahc2, awc2 = st.columns([3, 1])
                    a_l2 = ahc2.selectbox("Rally Leader 2", hero_list, index=0, key=f"wl2_{i}")
                    a_w2 = awc2.number_input("W2", 0, 10, 10, key=f"ww2_{i}")
                    
                    ahc3, awc3 = st.columns([3, 1])
                    a_l3 = ahc3.selectbox("Rally Leader 3", hero_list, index=0, key=f"wl3_{i}")
                    a_w3 = awc3.number_input("W3", 0, 10, 10, key=f"ww3_{i}")
                    
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
        mc_runs = st.number_input("MC Iterations per Combination", min_value=10, max_value=500, value=50, step=10)
        st.info("Note: Higher MC iterations provide more accuracy but will exponentially increase the time it takes to optimize the grid.")

        # =========================================================================
        # --- EXECUTION LOOP (GRID SEARCH OPTIMIZER) ---
        # =========================================================================
        if st.button("Run Optimization Engine"):
            with st.spinner("Executing Grid Search via Monte Carlo Engine..."):
                
                # Pre-build constant variables
                garrison_widgets = [g_wid1, g_wid2, g_wid3, 0, 0, 0, 0]
                g_widget_tot = sum(get_widget_bonus(lvl) for lvl in garrison_widgets)
                g_combat_stats = [
                    [g_inf_atk + g_widget_tot, g_inf_def + g_widget_tot, g_inf_let, g_inf_hp],
                    [g_cav_atk + g_widget_tot, g_cav_def + g_widget_tot, g_cav_let, g_cav_hp],
                    [g_arc_atk + g_widget_tot, g_arc_def + g_widget_tot, g_arc_let, g_arc_hp]
                ]
                
                # Pre-build Attacker Waves
                rally_waves_input = []
                for wave_idx in range(num_waves):
                    w_data = wave_configs[wave_idx]
                    w_widget_tot = sum(get_widget_bonus(lvl) for lvl in w_data["widgets"])
                    w_combat_stats = copy.deepcopy(w_data["stats"])
                    for row in range(3):
                        w_combat_stats[row][0] += w_widget_tot
                        w_combat_stats[row][1] += w_widget_tot
                        
                    wave_setup = TroopSide(
                        troops=w_data["troops"], stats=w_combat_stats,
                        leader_heroes=w_data["leaders"], supporter_heroes=w_data["supporters"],
                        tier=w_data["tier"], tg_level=w_data["tg"], widget_levels=w_data["widgets"]
                    )
                    rally_waves_input.append(wave_setup)

                results_grid = []

                # ---------------------------------------------------------
                # MODE 1: OPTIMIZE RATIOS
                # ---------------------------------------------------------
                if opt_mode == "Troop Ratios (Fixed Total Count)":
                    st.text("Generating Troop Ratio Grid (10% Steps)...")
                    
                    # Generate all permutations of (i, j, k) that sum to 10
                    ratio_grid = [(i/10.0, j/10.0, (10-i-j)/10.0) for i in range(11) for j in range(11-i)]
                    
                    progress_bar = st.progress(0)
                    for idx, ratios in enumerate(ratio_grid):
                        test_troops = [g_total_troops * ratios[0], g_total_troops * ratios[1], g_total_troops * ratios[2]]
                        
                        garrison_setup = TroopSide(
                            troops=test_troops, stats=g_combat_stats,
                            leader_heroes=[g_lead1, g_lead2, g_lead3], supporter_heroes=g_sup_heroes,
                            tier=g_tier, tg_level=g_tg, widget_levels=garrison_widgets
                        )
                        
                        tot_surv = 0
                        for _ in range(int(mc_runs)):
                            temp_g = copy.deepcopy(garrison_setup)
                            temp_w = copy.deepcopy(rally_waves_input)
                            final_g, _ = kingshot_multirally_sim2(temp_w, temp_g)
                            tot_surv += np.sum(final_g.troops)
                            
                        avg_surv = tot_surv / mc_runs
                        surv_pct = (avg_surv / max(1, g_total_troops)) * 100
                        results_grid.append({
                            "Configuration": f"Inf: {ratios[0]*100:.0f}% | Cav: {ratios[1]*100:.0f}% | Arc: {ratios[2]*100:.0f}%",
                            "Avg Remaining Troops": avg_surv,
                            "Survival Rate %": surv_pct
                        })
                        progress_bar.progress((idx + 1) / len(ratio_grid))

                # ---------------------------------------------------------
                # MODE 2: OPTIMIZE HEROES
                # ---------------------------------------------------------
                elif opt_mode == "Supporter Heroes (Fixed Troop Count)":
                    if not opt_hero_pool:
                        st.error("Please select at least one hero in the Joiner Pool.")
                        st.stop()
                        
                    st.text(f"Generating Hero Combinations from pool size {len(opt_hero_pool)}...")
                    
                    # Combinations with replacement (order doesn't matter, allows duplicates)
                    hero_combos = list(itertools.combinations_with_replacement(opt_hero_pool, 4))
                    
                    progress_bar = st.progress(0)
                    for idx, combo in enumerate(hero_combos):
                        garrison_setup = TroopSide(
                            troops=[g_inf, g_cav, g_arc], stats=g_combat_stats,
                            leader_heroes=[g_lead1, g_lead2, g_lead3], supporter_heroes=list(combo),
                            tier=g_tier, tg_level=g_tg, widget_levels=garrison_widgets
                        )
                        
                        tot_surv = 0
                        for _ in range(int(mc_runs)):
                            temp_g = copy.deepcopy(garrison_setup)
                            temp_w = copy.deepcopy(rally_waves_input)
                            final_g, _ = kingshot_multirally_sim2(temp_w, temp_g)
                            tot_surv += np.sum(final_g.troops)
                            
                        avg_surv = tot_surv / mc_runs
                        surv_pct = (avg_surv / max(1, g_total_troops)) * 100
                        results_grid.append({
                            "Configuration": f"{combo[0]}, {combo[1]}, {combo[2]}, {combo[3]}",
                            "Avg Remaining Troops": avg_surv,
                            "Survival Rate %": surv_pct
                        })
                        progress_bar.progress((idx + 1) / len(hero_combos))

                # =========================================================================
                # --- SORT AND DISPLAY LEADERBOARD ---
                # =========================================================================
                # Sort descending by max survivors
                sorted_results = sorted(results_grid, key=lambda x: x["Avg Remaining Troops"], reverse=True)
                
                st.success("Optimization Complete!")
                
                st.markdown("### Top 5 Optimal Configurations")
                top_5 = sorted_results[:5]
                formatted_top_5 = [{"Rank": i+1, "Configuration": r["Configuration"], "Avg Remaining Troops": f"{r['Avg Remaining Troops']:,.0f}"} for i, r in enumerate(top_5)]
                st.table(formatted_top_5)
                
                with st.expander("View Full Leaderboard"):
                    full_formatted = [{"Rank": i+1, "Configuration": r["Configuration"], "Avg Remaining Troops": f"{r['Avg Remaining Troops']:,.0f}"} for i, r in enumerate(sorted_results)]
                    st.dataframe(full_formatted, use_container_width=True)