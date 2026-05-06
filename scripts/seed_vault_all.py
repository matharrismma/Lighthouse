"""
seed_vault_all.py — 1000 seeds across all 48 domains.
One seed per known operation, with numeric variations for richness.
Run from repo root: python scripts/seed_vault_all.py
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from concordance_engine.mcp_server.tools import ALL_TOOLS
from api.packet_store import get_packet_store
from api.trust_index import record_confirmation
try:
    from concordance_engine.instance_identity import get_instance_id
    IID = get_instance_id() or "seed-all"
except Exception:
    IID = "seed-all"

store = get_packet_store()

def _v(tool_suffix, spec, *, fn_args=None):
    """Return (domain, spec, call_args) tuple."""
    return (tool_suffix, spec, fn_args)

SEEDS = []

# ── ACOUSTICS (30) ──────────────────────────────────────────────────────────
for f, wl, spd in [(440,0.773,340),(880,0.386,340),(261.63,1.304,340),(1000,0.343,343),(220,1.545,340),(100,3.43,343),(500,0.686,343)]:
    SEEDS.append(("acoustics", {"operation":"wave_relation","frequency_hz":f,"wavelength_m":wl,"claimed_speed_mps":spd}))
for p,db in [(2.0,40),(20.0,60),(200.0,80),(2000.0,100),(0.2,20)]:
    SEEDS.append(("acoustics", {"operation":"decibel_ratio","measured_pressure_Pa":p,"reference_pressure_Pa":0.00002,"claimed_db":db}))
for fund,n,claim in [(440,2,880),(440,3,1320),(261.63,2,523.26),(100,4,400),(880,2,1760)]:
    SEEDS.append(("acoustics", {"operation":"harmonic_frequency","fundamental_hz":fund,"harmonic_n":n,"claimed_hz":claim}))
for fs,vs,vo,fo in [(440,0,0,440),(440,10,0,453),(440,0,10,453),(1000,30,0,1094),(500,-20,0,472)]:
    SEEDS.append(("acoustics", {"operation":"doppler_shift","f_source_hz":fs,"v_source_mps":vs,"v_observer_mps":vo,"speed_medium_mps":343,"f_observed_hz":fo}))

# ── AGRICULTURE (20) ─────────────────────────────────────────────────────────
for crop,zone in [("tomato","6b"),("apple","5a"),("orange","9a"),("wheat","4b"),("cotton","7a")]:
    SEEDS.append(("agriculture", {"operation":"hardiness_zone","crop":crop,"claimed_zone":zone}))
for seq in [["corn","soybean","wheat"],["wheat","fallow","barley"],["potato","clover","oat"],["rice","legume","rice"]]:
    SEEDS.append(("agriculture", {"operation":"rotation","crop_sequence":seq,"duration_years":len(seq)}))
for crop,ph,suit in [("tomato",6.5,"suitable"),("blueberry",4.8,"suitable"),("wheat",6.0,"suitable"),("potato",5.5,"suitable"),("alfalfa",7.0,"suitable")]:
    SEEDS.append(("agriculture", {"operation":"soil_ph","crop":crop,"soil_ph":ph,"claimed_suitability":suit}))
for sp,area,rate in [("cattle",100,1.5),("sheep",50,5),("chicken",2,50),("goat",30,3),("pig",10,2),("horse",80,1)]:
    SEEDS.append(("agriculture", {"operation":"stocking_density","species":sp,"area_acres":area,"stocking_per_acre":rate}))

# ── ASTRONOMY (20) ──────────────────────────────────────────────────────────
for am,abm,dist in [(6.0,1.0,630),(8.5,3.0,500),(4.5,-1.0,2500),(10.0,5.0,1000),(7.0,2.0,794)]:
    SEEDS.append(("astronomy", {"operation":"distance_modulus","apparent_magnitude":am,"absolute_magnitude":abm,"claimed_distance_pc":dist}))
for p,a in [(1.0,1.0),(11.86,5.2),(0.615,0.723),(29.46,9.54),(84.01,19.19)]:
    SEEDS.append(("astronomy", {"operation":"kepler_third_law","orbital_period_years":p,"semi_major_axis_au":a}))
for par,dist in [(0.7724,1.295),(0.3086,3.24),(0.5495,1.82),(1.0,1.0),(0.2246,4.45)]:
    SEEDS.append(("astronomy", {"operation":"parallax_distance","parallax_arcsec":par,"claimed_distance_pc":dist}))
for m1,m2,sep,f in [(1.989e30,5.972e24,1.496e11,3.54e22),(5.972e24,7.346e22,3.844e8,1.98e20),(1.989e30,1.989e30,1e10,2.65e20)]:
    SEEDS.append(("astronomy", {"operation":"gravitational_force","mass_1_kg":m1,"mass_2_kg":m2,"separation_m":sep,"claimed_force_N":f}))
for p2,a2 in [(0.241,0.387),(1.881,1.524)]:
    SEEDS.append(("astronomy", {"operation":"kepler_third_law","orbital_period_years":p2,"semi_major_axis_au":a2}))

# ── BIOLOGY (15) ────────────────────────────────────────────────────────────
for obs,exp in [([10,10,10,10],[10,10,10,10]),([25,25,25,25],[25,25,25,25]),([50,50],[50,50])]:
    SEEDS.append(("biology", {"operation":"hardy_weinberg","observed":obs,"expected":exp}))
for n,mn in [(3,3),(5,5),(10,10),(6,6),(4,4)]:
    SEEDS.append(("biology", {"operation":"replicates","n_replicates":n,"min_replicates":mn}))
for doses,resp in [([0,1,10,100],[0,5,50,90]),([0,0.1,1,10],[0,10,60,95]),([0,5,50],[0,30,80])]:
    SEEDS.append(("biology", {"operation":"dose_response_monotonicity","doses":doses,"responses":resp}))
SEEDS.append(("biology", {"operation":"sample_size_powered","effect_size":0.5,"alpha":0.05,"n_per_group":64}))
SEEDS.append(("biology", {"operation":"sample_size_powered","effect_size":0.8,"alpha":0.05,"n_per_group":26}))
SEEDS.append(("biology", {"operation":"molarity","solute_g":18,"molar_mass_g_mol":18,"volume_L":1.0,"claimed_M":1.0}))
SEEDS.append(("biology", {"operation":"molarity","solute_g":58.44,"molar_mass_g_mol":58.44,"volume_L":1.0,"claimed_M":1.0}))

# ── CALENDAR_TIME (20) ──────────────────────────────────────────────────────
for yr,leap in [(2024,True),(2023,False),(2000,True),(1900,False),(2100,False),(2400,True),(2020,True),(2019,False)]:
    SEEDS.append(("calendar_time", {"operation":"leap_year","year":yr,"claimed_leap":leap}))
for d,dow in [("2026-01-01","Thursday"),("2026-05-06","Wednesday"),("2000-01-01","Saturday"),("2024-12-25","Wednesday")]:
    SEEDS.append(("calendar_time", {"operation":"day_of_week","date_iso":d,"claimed_day_of_week":dow}))
SEEDS.append(("calendar_time", {"operation":"iso","iso8601_string":"2026-05-06T12:00:00Z"}))
SEEDS.append(("calendar_time", {"operation":"iso","iso8601_string":"2000-01-01T00:00:00Z"}))
SEEDS.append(("calendar_time", {"operation":"duration_addition","start_iso":"2026-01-01T00:00:00Z","duration_seconds":86400,"claimed_end_iso":"2026-01-02T00:00:00Z"}))
SEEDS.append(("calendar_time", {"operation":"duration_addition","start_iso":"2026-06-01T00:00:00Z","duration_seconds":3600,"claimed_end_iso":"2026-06-01T01:00:00Z"}))
SEEDS.append(("calendar_time", {"operation":"day_of_week","date_iso":"2026-12-25","claimed_day_of_week":"Friday"}))
SEEDS.append(("calendar_time", {"operation":"leap_year","year":2028,"claimed_leap":True}))

# ── CHEMISTRY (25) ──────────────────────────────────────────────────────────
for ph,cls in [(1.0,"strong_acid"),(3.5,"weak_acid"),(7.0,"neutral"),(10.5,"weak_base"),(13.0,"strong_base"),(6.8,"weak_acid"),(4.0,"acid"),(9.0,"base")]:
    SEEDS.append(("chemistry", {"operation":"ph_classification","pH":ph,"claimed_classification":cls}))
for eq in ["H2 + Cl2 -> 2HCl","2H2 + O2 -> 2H2O","CH4 + 2O2 -> CO2 + 2H2O","N2 + 3H2 -> 2NH3","2Na + 2H2O -> 2NaOH + H2","CaCO3 -> CaO + CO2","Fe2O3 + 3CO -> 2Fe + 3CO2"]:
    SEEDS.append(("chemistry", {"operation":"equation","equation":eq}))
for dh,ds,t,feas in [(-100,50,298,True),(-200,-100,298,True),(100,-50,298,False),(50,200,298,True),(-50,-100,500,True)]:
    SEEDS.append(("chemistry", {"operation":"thermodynamic_feasibility","delta_H_kJ_mol":dh,"delta_S_J_mol_K":ds,"temperature_K":t,"claimed_feasible":feas}))
for t_k in [273.15,298.15,373.15,500,1000]:
    SEEDS.append(("chemistry", {"operation":"temperature","temperature_K":t_k}))

# ── COMBINATORICS (20) ──────────────────────────────────────────────────────
for n,k,c in [(5,2,10),(10,3,120),(6,3,20),(8,4,70),(12,5,792),(4,2,6),(7,3,35),(9,4,126)]:
    SEEDS.append(("combinatorics", {"operation":"combinations","comb_n":n,"comb_k":k,"claimed_combinations":c}))
for n,k,p in [(5,2,20),(4,3,24),(6,2,30),(7,3,210),(3,3,6),(8,2,56),(10,2,90),(9,3,504)]:
    SEEDS.append(("combinatorics", {"operation":"permutations","perm_n":n,"perm_k":k,"claimed_permutations":p}))
for n,d in [(1,1),(2,1),(3,2),(4,9),(5,44)]:
    SEEDS.append(("combinatorics", {"operation":"derangements","derangement_n":n,"claimed_derangements":d}))

# ── CONSTRUCTION (30) ───────────────────────────────────────────────────────
for l,w,d,v in [(10,5,0.15,7.5),(6,4,0.2,4.8),(20,8,0.1,16),(3,3,0.3,2.7),(15,6,0.12,10.8),(12,10,0.15,18)]:
    SEEDS.append(("construction", {"operation":"concrete_volume","length_m":l,"width_m":w,"depth_m":d,"claimed_volume_m3":v}))
for l,w,a in [(10,5,50),(6,4,24),(12,8,96),(3,3,9),(20,15,300),(7,4,28)]:
    SEEDS.append(("construction", {"operation":"rectangular_area","length_m":l,"width_m":w,"claimed_area_m2":a}))
for r,a in [(5,78.54),(3,28.27),(7,153.94),(1,3.14),(10,314.16),(4,50.27)]:
    SEEDS.append(("construction", {"operation":"circular_area","radius_m":r,"claimed_area_m2":a}))
for rl,ruw,rw in [(100,0.888,88.8),(50,0.617,30.85),(200,1.578,315.6),(75,0.395,29.6)]:
    SEEDS.append(("construction", {"operation":"rebar_weight","rebar_length_m":rl,"rebar_unit_weight_kg_per_m":ruw,"claimed_weight_kg":rw}))
for l,h,op,a in [(6,3,4,14),(10,4,8,32),(5,2.5,2,10.5),(8,3,6,18)]:
    SEEDS.append(("construction", {"operation":"wall_area","length_m":l,"height_m":h,"openings_m2":op,"claimed_net_area_m2":a}))
for a,cov,cans in [(80,10,8),(120,12,10),(50,8,7),(200,15,14)]:
    SEEDS.append(("construction", {"operation":"paint_coverage","paint_area_m2":a,"coverage_m2_per_can":cov,"claimed_cans":cans}))
for ra,ta,waste,tiles in [(20,0.36,10,62),(30,0.25,10,133),(15,0.09,5,175),(50,1.0,10,56)]:
    SEEDS.append(("construction", {"operation":"floor_tiles","room_area_m2":ra,"tile_area_m2":ta,"waste_pct":waste,"claimed_tiles":tiles}))
for span,load,moment in [(5,12,37.5),(4,10,20),(6,8,36),(3,15,16.9)]:
    SEEDS.append(("construction", {"operation":"beam_load","span_m":span,"load_kN_per_m":load,"claimed_moment_kNm":moment}))

# ── CRYPTOGRAPHY (30) ───────────────────────────────────────────────────────
import hashlib as _hl
for txt,algo,h in [
    ("hello","sha256",_hl.sha256(b"hello").hexdigest()),
    ("concordance","sha256",_hl.sha256(b"concordance").hexdigest()),
    ("","sha256",_hl.sha256(b"").hexdigest()),
    ("abc","sha256",_hl.sha256(b"abc").hexdigest()),
    ("test","sha256",_hl.sha256(b"test").hexdigest()),
    ("hello","sha512",_hl.sha512(b"hello").hexdigest()),
    ("concordance","sha512",_hl.sha512(b"concordance").hexdigest()),
    ("","md5",_hl.md5(b"").hexdigest()),
    ("hello","md5",_hl.md5(b"hello").hexdigest()),
    ("abc","sha1",_hl.sha1(b"abc").hexdigest()),
]:
    SEEDS.append(("cryptography", {"operation":"hash_match","data":txt,"hash_algorithm":algo,"claimed_hash_hex":h}))
for bits,strong in [(2048,True),(4096,True),(1024,False),(512,False),(256,False),(3072,True),(768,False),(8192,True)]:
    SEEDS.append(("cryptography", {"operation":"key_strength","key_bits":bits,"claimed_strong":strong}))
for enc,dec in [("aGVsbG8=","hello"),("Y29uY29yZGFuY2U=","concordance"),("dGVzdA==","test"),("YWJj","abc"),("d29ybGQ=","world")]:
    SEEDS.append(("cryptography", {"operation":"encoding_roundtrip","encoded":enc,"cipher":"base64","claimed_decoded":dec}))
for h_algo in ["sha256","sha512","sha3_256","blake2b","sha1","md5","sha224","sha384"]:
    SEEDS.append(("cryptography", {"operation":"hash_strength","hash_algorithm":h_algo}))

# ── CYBERSECURITY (30) ──────────────────────────────────────────────────────
for pw,ln,cs in [("abc123",6,36),("P@ssw0rd!",9,72),("correct-horse-battery-staple",28,26),("Tr0ub4dor&3",11,72),("12345678",8,10),("qwerty",6,26),("C0nc0rd@nce2026!",16,72),("letmein",7,26)]:
    SEEDS.append(("cybersecurity", {"operation":"password_entropy","password_length":ln,"charset_size":cs}))
for port,cls in [(80,"http"),(443,"https"),(22,"ssh"),(3306,"database"),(5432,"database"),(53,"dns"),(25,"smtp"),(3389,"rdp"),(8080,"http-alt"),(21,"ftp")]:
    SEEDS.append(("cybersecurity", {"operation":"port_class","port_number":port,"claimed_port_class":cls}))
for cidr,hosts in [(24,254),(16,65534),(8,16777214),(25,126),(28,14),(29,6),(30,2),(27,30)]:
    SEEDS.append(("cybersecurity", {"operation":"subnet_hosts","cidr_prefix":cidr,"claimed_host_count":hosts}))
for tls,ok in [("1.3",True),("1.2",True),("1.1",False),("1.0",False),("SSL3",False),("1.3",True),("1.2",True)]:
    SEEDS.append(("cybersecurity", {"operation":"tls_version","tls_version":tls,"claimed_secure":ok}))
for score,sev in [(9.8,"critical"),(7.5,"high"),(4.0,"medium"),(2.1,"low"),(0.0,"none"),(10.0,"critical")]:
    SEEDS.append(("cybersecurity", {"operation":"cvss_severity","cvss_base_score":score,"claimed_severity":sev}))

# ── DOCUMENT_VALIDATION (15) ─────────────────────────────────────────────────
for isbn in ["978-0-306-40615-7","978-3-16-148410-0","978-0-7432-7356-5","0-306-40615-2","0-7432-7356-7"]:
    SEEDS.append(("document_validation", {"operation":"isbn","isbn13":isbn}))
for n,v in [("4532015112830366",True),("1234567890123456",False),("4111111111111111",True),("79927398713",True),("79927398714",False)]:
    SEEDS.append(("document_validation", {"operation":"luhn","luhn_number":n,"claimed_valid":v}))
for ean in ["4006381333931","5901234123457","0012345678905","0075678164125","0885909950447"]:
    SEEDS.append(("document_validation", {"operation":"ean_upc","ean_or_upc":ean}))

# ── ECONOMICS (29) ──────────────────────────────────────────────────────────
for p,r,y,r2 in [(1000,0.05,3,150),(5000,0.04,5,1000),(10000,0.07,10,7000),(500,0.06,2,60),(2000,0.03,4,240)]:
    SEEDS.append(("economics", {"operation":"simple_interest","principal":p,"rate":r,"years":y,"claimed_interest":r2}))
for p,r,n,y,fv in [(1000,0.07,12,10,2009.66),(5000,0.05,1,20,13266.5),(10000,0.06,4,30,60226.0),(1000,0.10,1,5,1610.51),(2000,0.08,2,15,6570.0)]:
    SEEDS.append(("economics", {"operation":"compound_interest","principal":p,"rate":r,"compounding_periods":n,"years":y,"claimed_future_value":fv}))
for r,dbl in [(8,9),(6,12),(10,7.2),(5,14.4),(12,6),(4,18),(7,10.3)]:
    SEEDS.append(("economics", {"operation":"rule_of_70","rate":r,"claimed_doubling_years":dbl}))
for gdp,pop,pc in [(21000000000000,331000000,63444),(3700000000000,1400000000,2643),(2900000000000,1380000000,2101),(1800000000000,211000000,8531)]:
    SEEDS.append(("economics", {"operation":"gdp_per_capita","gdp":gdp,"population":pop,"claimed_per_capita":pc}))
for pq,pp,pe in [(-10,5,-2.0),(-5,10,-0.5),(-20,10,-2.0),(10,-5,-2.0),(-3,6,-0.5)]:
    SEEDS.append(("economics", {"operation":"price_elasticity","pct_change_quantity":pq,"pct_change_price":pp,"claimed_elasticity":pe}))
for fv,r,y,pv in [(10000,0.06,5,7472.58),(50000,0.08,10,23159.67),(1000,0.05,3,863.84),(20000,0.07,20,5169.0)]:
    SEEDS.append(("economics", {"operation":"present_value","future_value":fv,"rate":r,"years":y,"claimed_pv":pv}))

# ── ELECTRICAL (20) ──────────────────────────────────────────────────────────
for v,i,r in [(12,3,4),(120,10,12),(9,0.5,18),(240,20,12),(5,0.1,50),(24,4,6),(110,5,22),(48,8,6)]:
    SEEDS.append(("electrical", {"operation":"ohms_law","voltage_V":v,"current_A":i,"resistance_ohm":r}))
for v,i,p in [(120,15,1800),(240,10,2400),(12,5,60),(9,2,18),(110,8,880),(24,3,72)]:
    SEEDS.append(("electrical", {"operation":"power","voltage_V":v,"current_A":i,"power_W_claim":p}))
for voltages,ok in [([12,-12],True),([5,-3,-2],True),([10,-8,-2],True),([9,-5,-4],True),([120,-120],True)]:
    SEEDS.append(("electrical", {"operation":"kirchhoff_voltage_loop","voltages_in_loop":voltages,"claimed_sums_to_zero":ok}))
for r,c,t,v in [(1000,0.001,1.0,0.632),(10000,0.0001,1.0,0.632),(500,0.002,1.0,0.632)]:
    SEEDS.append(("electrical", {"operation":"rc_time_constant","resistance_ohm":r,"capacitance_F":c,"elapsed_s":t,"claimed_fraction":v}))

# ── ENERGY (25) ──────────────────────────────────────────────────────────────
for bwh,ckd,days in [(10000,2.0,5),(5000,1.0,5),(20000,4.0,5),(2000,0.5,4),(15000,3.0,5)]:
    SEEDS.append(("energy", {"operation":"battery_sizing","battery_wh":bwh,"consumption_kwh_day":ckd,"claimed_days_autonomy":days}))
for inp,out,eff in [(1000,850,0.85),(2000,1600,0.80),(500,450,0.90),(100,97,0.97),(3000,2100,0.70)]:
    SEEDS.append(("energy", {"operation":"efficiency","input_W":inp,"output_W":out,"claimed_efficiency":eff}))
for bwh,load,hrs in [(10000,500,20),(5000,250,20),(2000,100,20),(20000,1000,20),(8000,400,20)]:
    SEEDS.append(("energy", {"operation":"runtime","battery_wh":bwh,"load_W":load,"claimed_hours":hrs}))
for gen,cons,ok in [(20,15,True),(10,12,False),(30,30,True),(25,20,True),(5,8,False)]:
    SEEDS.append(("energy", {"operation":"power_balance","generation_kwh_day":gen,"consumption_kwh_day":cons,"claimed_surplus":ok}))
for panels,hrs,eff,kwh in [(10,5,0.85,42.5),(20,6,0.90,108),(5,4,0.80,16),(15,5,0.85,63.75),(8,5,0.85,34)]:
    SEEDS.append(("energy", {"operation":"solar_daily_yield","panel_watts":panels*400,"hours_sun":hrs,"efficiency":eff,"claimed_kwh":kwh}))

# ── EXERCISE_SCIENCE (20) ────────────────────────────────────────────────────
for age,mhr in [(20,200),(30,190),(40,180),(50,170),(60,160),(25,195),(35,185),(45,175)]:
    SEEDS.append(("exercise_science", {"operation":"max_heart_rate","age_years":age,"claimed_max_hr":mhr}))
for age,wt,act,dur,kcal in [(30,70,"running",1.0,600),(40,80,"cycling",1.0,500),(25,60,"swimming",0.5,250),(50,90,"walking",1.0,350)]:
    SEEDS.append(("exercise_science", {"operation":"energy_expenditure","age_years":age,"weight_kg":wt,"activity":act,"duration_hours":dur,"claimed_kcal":kcal}))
for rest,lo,hi in [(60,114,133),(70,118,137),(55,110,128),(65,116,134),(75,120,140),(50,108,126)]:
    SEEDS.append(("exercise_science", {"operation":"target_heart_rate_zone","resting_hr":rest,"intensity_low":0.5,"intensity_high":0.6,"claimed_lo":lo,"claimed_hi":hi}))
for act,met in [("running",8.0),("cycling",6.0),("walking",3.5),("swimming",7.0),("yoga",2.5),("weight_training",3.5)]:
    SEEDS.append(("exercise_science", {"operation":"met_lookup","activity":act,"claimed_met":met}))

# ── FINANCE (30) ─────────────────────────────────────────────────────────────
for cf,r,npv in [
    ([-1000,300,400,500],0.10,(-1000+300/1.1+400/1.21+500/1.331)),
    ([-5000,2000,2000,2000],0.08,(-5000+2000/1.08+2000/1.166+2000/1.26)),
    ([-10000,4000,4000,4000,4000],0.12,(-10000+4000/1.12+4000/1.254+4000/1.405+4000/1.574)),
]:
    SEEDS.append(("finance", {"operation":"npv","cashflows":cf,"discount_rate":r,"claimed_npv":round(npv,2)}))
for p,r,y,fv in [(1000,0.07,10,1967.15),(5000,0.05,20,13266.5),(10000,0.06,5,13382.26),(2000,0.08,15,6342.0)]:
    SEEDS.append(("finance", {"operation":"compound_interest","principal":p,"rate":r,"years":y,"claimed_fv":fv}))
for fv,r,y,pv in [(10000,0.06,5,7472.58),(50000,0.08,10,23159.67),(1000,0.05,3,863.84),(20000,0.07,20,5169.0)]:
    SEEDS.append(("finance", {"operation":"present_value","future_value":fv,"rate":r,"years":y,"claimed_pv":pv}))
for a,l,e,ok in [(100000,60000,40000,True),(500000,200000,300000,True),(1000000,1000000,0,True),(75000,50000,25000,True)]:
    SEEDS.append(("finance", {"operation":"accounting_identity","assets":a,"liabilities":l,"equity":e,"claimed_balanced":ok}))
for p,r,y,fv in [(1000,0.10,5,1610.51),(2000,0.08,10,4317.85),(500,0.06,20,1603.57),(10000,0.05,30,43219.42)]:
    SEEDS.append(("finance", {"operation":"compound_interest","principal":p,"rate":r,"years":y,"claimed_fv":fv}))
for a2,l2,e2 in [(200000,80000,120000),(1500000,900000,600000),(50000,20000,30000),(300000,150000,150000)]:
    SEEDS.append(("finance", {"operation":"accounting_identity","assets":a2,"liabilities":l2,"equity":e2,"claimed_balanced":True}))
for cf2,r2,npv2 in [
    ([-2000,800,800,800],0.10,(-2000+800/1.1+800/1.21+800/1.331)),
    ([-500,200,200,200],0.05,(-500+200/1.05+200/1.1025+200/1.157)),
    ([-8000,3000,3000,3000,3000],0.15,(-8000+3000/1.15+3000/1.322+3000/1.521+3000/1.749)),
]:
    SEEDS.append(("finance", {"operation":"npv","cashflows":cf2,"discount_rate":r2,"claimed_npv":round(npv2,2)}))
for a3,l3,e3 in [(900000,450000,450000),(2000000,1200000,800000),(400000,100000,300000)]:
    SEEDS.append(("finance", {"operation":"accounting_identity","assets":a3,"liabilities":l3,"equity":e3,"claimed_balanced":True}))

# ── FORMAL_LOGIC (30) ────────────────────────────────────────────────────────
tautologies = ["P OR NOT P","(P AND Q) OR (NOT P) OR (NOT Q)","P OR (NOT P AND Q) OR (NOT P AND NOT Q)",
                "(P -> Q) OR (Q -> P)","NOT (P AND NOT P)","P -> P","(P AND Q) -> P"]
for f in tautologies:
    SEEDS.append(("formal_logic", {"operation":"tautology","formula":f,"claimed_tautology":True}))
contradictions = ["P AND NOT P","(P -> Q) AND P AND NOT Q","(P OR Q) AND NOT P AND NOT Q"]
for f in contradictions:
    SEEDS.append(("formal_logic", {"operation":"contradiction","formula":f,"claimed_contradiction":True}))
entailments = [
    (["P","P -> Q"],"Q",True),
    (["P OR Q","NOT P"],"Q",True),
    (["ALL x: M(x) -> D(x)","M(s)"],"D(s)",True),
    (["NOT Q","P -> Q"],"NOT P",True),
    (["P AND Q"],"P",True),
    (["P AND Q"],"Q",True),
    (["P"],"P OR Q",True),
    (["NOT NOT P"],"P",True),
]
for prems,conc,ok in entailments:
    SEEDS.append(("formal_logic", {"operation":"entailment","premises":prems,"conclusion":conc,"claimed_entails":ok}))
equivs = [
    ("P AND (P OR Q)","P",True),
    ("NOT (P AND Q)","NOT P OR NOT Q",True),
    ("P -> Q","NOT P OR Q",True),
    ("NOT NOT P","P",True),
    ("P AND Q","Q AND P",True),
]
for a,b,ok in equivs:
    SEEDS.append(("formal_logic", {"operation":"equivalence","formula_a":a,"formula_b":b,"claimed_equivalent":ok}))
SEEDS.append(("formal_logic", {"operation":"satisfiability","formula":"P AND NOT P","claimed_satisfiable":False}))
SEEDS.append(("formal_logic", {"operation":"satisfiability","formula":"P OR Q","claimed_satisfiable":True}))
SEEDS.append(("formal_logic", {"operation":"satisfiability","formula":"P","claimed_satisfiable":True}))
SEEDS.append(("formal_logic", {"operation":"satisfiability","formula":"NOT P AND P","claimed_satisfiable":False}))
SEEDS.append(("formal_logic", {"operation":"satisfiability","formula":"P AND Q","claimed_satisfiable":True}))

# ── GENETICS (25) ────────────────────────────────────────────────────────────
for seq,gc in [("ATCGATCG",50.0),("GCGCGCGC",100.0),("ATATATATAT",0.0),("GGATCC",66.7),("AGTCAGTC",50.0),("GCATGCAT",50.0)]:
    SEEDS.append(("genetics", {"operation":"gc_content","sequence":seq,"claimed_gc_fraction":round(gc/100,3)}))
for codon,aa in [("AUG","Met"),("UAA","Stop"),("UAG","Stop"),("UGA","Stop"),("GCU","Ala"),("CGU","Arg"),("AAA","Lys"),("UUU","Phe")]:
    SEEDS.append(("genetics", {"operation":"codon_amino_acid","codon":codon,"claimed_amino_acid":aa}))
for seq,rc in [("ATCG","CGAT"),("GGATCC","GGATCC"),("AATT","AATT"),("GCGC","GCGC"),("ATCGATCG","CGATCGAT")]:
    SEEDS.append(("genetics", {"operation":"reverse_complement","sequence":seq,"claimed_rc":rc}))
for seq,comp in [("ATCG","TAGC"),("GCGC","CGCG"),("AATT","TTAA"),("GGATCC","CCTAGG")]:
    SEEDS.append(("genetics", {"operation":"complementarity","sequence":seq,"claimed_complement":comp}))
for rna,aa in [("AUG-GCU-UAA","Met-Ala-Stop"),("UUU-GGG","Phe-Gly"),("AAA-CCC","Lys-Pro")]:
    SEEDS.append(("genetics", {"operation":"codon_translation","rna":rna,"claimed_protein":aa}))

# ── GEOGRAPHY (30) ──────────────────────────────────────────────────────────
cities = [
    (40.7128,-74.0060,51.5074,-0.1278,5570.0),
    (48.8566,2.3522,35.6762,139.6503,9716.0),
    (-33.8688,151.2093,51.5074,-0.1278,16993.0),
    (0,0,0,90,10007.5),
    (40.7128,-74.0060,34.0522,-118.2437,3940.0),
    (55.7558,37.6173,39.9042,116.4074,5800.0),
    (19.4326,-99.1332,40.7128,-74.0060,3360.0),
    (-22.9068,-43.1729,-34.6037,-58.3816,2818.0),
]
for row in cities:
    SEEDS.append(("geography", {"operation":"haversine_distance","lat1":row[0],"lon1":row[1],"lat2":row[2],"lon2":row[3],"claimed_distance_km":row[4]}))
for lat,lon,ok in [(90,0,True),(-90,180,True),(0,360,False),(91,0,False),(40.7128,-74.0060,True),(48.8566,2.3522,True),(0,0,True),(-33.8688,151.2093,True)]:
    SEEDS.append(("geography", {"operation":"lat_lon_validity","lat":lat,"lon":lon,"claimed_valid":ok}))
for lat,lon,z in [(0,0,"31N"),(48.8566,2.3522,"31U"),(40.7128,-74.0060,"18T"),(51.5074,-0.1278,"30U")]:
    SEEDS.append(("geography", {"operation":"utm_zone","lat":lat,"lon":lon,"claimed_zone":z}))
for lat1,lon1,lat2,lon2,bear in [(0,0,0,90,90),(0,0,90,0,0),(0,0,-90,0,180),(0,0,0,-90,270)]:
    SEEDS.append(("geography", {"operation":"initial_bearing","lat1":lat1,"lon1":lon1,"lat2":lat2,"lon2":lon2,"claimed_bearing_deg":bear}))

# ── GEOLOGY (25) ─────────────────────────────────────────────────────────────
for s,h,ok in [(2.0,7.0,True),(5.0,7.0,True),(1.0,10.0,True),(6.5,7.0,True),(3.0,3.0,False),(7.0,6.0,False),(4.5,6.0,True),(2.5,4.0,True)]:
    SEEDS.append(("geology", {"operation":"mohs_scratch","softer_mineral_mohs":s,"harder_mineral_mohs":h,"claimed_harder_scratches":ok}))
for m1,m2,amp in [(5.0,6.0,10),(4.0,6.0,100),(6.0,8.0,100),(5.0,7.0,100),(3.0,5.0,100)]:
    SEEDS.append(("geology", {"operation":"richter_amplitude","richter_M1":m1,"richter_M2":m2,"claimed_amplitude_ratio":amp}))
for init,yrs,hl,rem in [(100,5730,5730,50.0),(200,14000,5730,73.0),(1000,28650,5730,125.0),(100,1000,5730,88.5),(500,10000,1600,356.0)]:
    SEEDS.append(("geology", {"operation":"radiometric_decay","initial_amount":init,"elapsed_years":yrs,"isotope_half_life_years":hl,"claimed_remaining":rem}))
for s2,h2 in [(1.0,2.5),(3.5,5.0),(6.0,9.0),(4.0,7.5),(2.0,3.0),(8.0,9.5),(5.5,6.5),(7.0,10.0)]:
    SEEDS.append(("geology", {"operation":"mohs_scratch","softer_mineral_mohs":s2,"harder_mineral_mohs":h2,"claimed_harder_scratches":True}))

# ── GEOMETRY (20) ────────────────────────────────────────────────────────────
for a,b,c,ok in [(3,4,5,True),(5,12,13,True),(8,15,17,True),(7,24,25,True),(6,8,10,True),(9,40,41,True),(10,24,26,True)]:
    SEEDS.append(("geometry", {"operation":"pythagorean","pyth_a":a,"pyth_b":b,"pyth_c":c,"claimed_right_triangle":ok}))
for a,b,c,ok in [(1,2,3,False),(1,1,3,False),(2,2,5,False)]:
    SEEDS.append(("geometry", {"operation":"triangle_inequality","tri_a":a,"tri_b":b,"tri_c":c,"claimed_valid":ok}))
for n,sum_ang in [(3,180),(4,360),(5,540),(6,720),(8,1080),(10,1440),(12,1800)]:
    SEEDS.append(("geometry", {"operation":"polygon_angle_sum","polygon_n":n,"claimed_sum_degrees":sum_ang}))
for r,area,circ in [(5,78.54,31.42),(3,28.27,18.85),(7,153.94,43.98),(1,3.14,6.28),(10,314.16,62.83)]:
    SEEDS.append(("geometry", {"operation":"circle_properties","circle_radius":r,"claimed_area":area,"claimed_circumference":circ}))

# ── GOVERNANCE (10) ──────────────────────────────────────────────────────────
for dec,rat,alts,wc in [
    ("Adopt open-source license","Maximizes reach and trust",["proprietary","CC-BY"],5),
    ("Release quarterly reports","Transparency to stakeholders",["annual","on-demand"],7),
    ("Require two-factor auth","Security baseline for all accounts",["password-only","biometric"],4),
    ("Freeze non-critical merges","Mobile release branch cut",["rolling","monthly"],3),
    ("Adopt RFC process for API changes","Prevents breaking changes",["ad-hoc","design-docs-only"],6),
    ("Establish incident post-mortems","Learning from failures",["blame-free","root-cause-only"],5),
    ("Mandate code review","Quality gate before merge",["optional","pair-only"],8),
    ("Set 30-day retention for logs","Balances cost and compliance",["7-day","90-day","indefinite"],4),
    ("Require changelog entries","Audit trail for all changes",["optional","commit-only"],3),
    ("Adopt SPDX license headers","Machine-readable license compliance",["README-only","NOTICE-file"],5),
]:
    SEEDS.append(("governance_decision_packet", dec, rat, alts, wc))

# ── HYDROLOGY (20) ──────────────────────────────────────────────────────────
for k,grad,v in [(0.001,0.01,0.00001),(0.01,0.05,0.0005),(0.0001,0.1,0.00001),(0.05,0.02,0.001),(0.005,0.03,0.00015)]:
    SEEDS.append(("hydrology", {"operation":"darcy_velocity","darcy_K_m_s":k,"hydraulic_gradient":grad,"claimed_velocity_m_s":v}))
for mn,r,s,v in [(0.013,0.5,0.001,19.2),(0.025,1.0,0.005,32.8),(0.035,0.3,0.002,7.7),(0.010,2.0,0.010,127.2),(0.020,0.8,0.003,36.2)]:
    SEEDS.append(("hydrology", {"operation":"manning_velocity","manning_n":mn,"hydraulic_radius_m":r,"slope":s,"claimed_velocity_m_s":v}))
for ri,rc,da,q in [(25,0.6,100,1.5),(50,0.7,200,7.0),(10,0.5,500,5.0),(30,0.8,150,3.6),(20,0.4,300,2.4)]:
    SEEDS.append(("hydrology", {"operation":"rational_runoff","rainfall_intensity":ri,"runoff_coefficient":rc,"drainage_area":da,"claimed_runoff":q}))
for v2,z,p,h in [(5,0.5,50000,2.78),(10,1.0,101325,6.09),(3,0.2,20000,1.66),(7,0.7,70000,4.08)]:
    SEEDS.append(("hydrology", {"operation":"bernoulli_head","velocity_m_s":v2,"elevation_m":z,"pressure_Pa":p,"claimed_total_head_m":h}))

# ── INFORMATION_THEORY (15) ──────────────────────────────────────────────────
for probs,ent in [
    ([0.5,0.5],1.0),([0.25,0.25,0.25,0.25],2.0),([1.0],0.0),
    ([0.5,0.25,0.125,0.125],1.75),([0.7,0.3],0.881),
]:
    SEEDS.append(("information_theory", {"operation":"shannon_entropy","probabilities":probs,"claimed_entropy_bits":ent}))
for a,b,d in [("hello","hello",0),("hello","hxllo",1),("hello","world",4),("abcd","abce",1),("1234","5678",4)]:
    SEEDS.append(("information_theory", {"operation":"hamming_distance","string_a":a,"string_b":b,"claimed_distance":d}))
for err,cap in [(0.1,0.531),(0.2,0.278),(0.5,0.0),(0.01,0.919),(0.05,0.714),(0.3,0.119)]:
    SEEDS.append(("information_theory", {"operation":"bsc_capacity","bsc_error_rate":err,"claimed_capacity":cap}))
for p,e in [([0.8,0.2],0.722),([0.9,0.1],0.469),([0.6,0.4],0.971)]:
    SEEDS.append(("information_theory", {"operation":"shannon_entropy","probabilities":p,"claimed_entropy_bits":e}))

# ── LABOR (25) ───────────────────────────────────────────────────────────────
for hr,hrs,gross in [(18,40,720),(25,35,875),(12,40,480),(40,40,1600),(15,38,570),(22,40,880),(50,40,2000)]:
    SEEDS.append(("labor", {"operation":"gross_pay","hourly_rate":hr,"hours_worked":hrs,"claimed_gross":gross}))
for hr,rh,oh,pay in [(18,40,8,871.2),(25,40,5,1187.5),(15,40,10,675),(20,40,4,920),(30,40,6,1470)]:
    SEEDS.append(("labor", {"operation":"overtime_pay","hourly_rate":hr,"regular_hours":rh,"overtime_hours":oh,"claimed_total_pay":pay}))
for ann,hrly in [(52000,25.0),(40000,19.23),(80000,38.46),(36000,17.31),(60000,28.85),(100000,48.08)]:
    SEEDS.append(("labor", {"operation":"annual_to_hourly","annual_salary":ann,"claimed_hourly":hrly}))
for gross,tax,ded,net in [(800,0.22,50,574),(1500,0.25,100,1025),(2000,0.28,150,1290),(500,0.15,25,400)]:
    SEEDS.append(("labor", {"operation":"take_home_pay","gross_pay":gross,"total_tax_rate":tax,"deductions":ded,"claimed_net":net}))
for rate,thresh,ok in [(7.25,7.25,True),(10.0,7.25,True),(6.50,7.25,False),(15.0,7.25,True),(7.24,7.25,False)]:
    SEEDS.append(("labor", {"operation":"minimum_wage_check","hourly_rate":rate,"minimum_wage_threshold":thresh,"claimed_compliant":ok}))

# ── LINGUISTICS (15) ─────────────────────────────────────────────────────────
for w,t,d in [
    ("love","agape","strong selfless love"),("word","logos","reason, word, principle"),
    ("truth","aletheia","unconcealment, truth"),("grace","charis","favor, gift"),
    ("peace","shalom","wholeness, completeness"),("faith","pistis","trust, faithfulness"),
]:
    SEEDS.append(("linguistics", {"operation":"gloss","word":w,"transliteration":t,"definition":d}))
for w,wc in [("The quick brown fox",4),("Concordance engine verifies truth",4),("Hello world",2),("One",1)]:
    SEEDS.append(("linguistics", {"operation":"word_count","word":w,"claimed_count":wc}))
for w,t in [("love","ahavah"),("peace","shalom"),("truth","emet"),("king","melek"),("light","or")]:
    SEEDS.append(("linguistics", {"operation":"transliteration_normalized_match","word":w,"transliteration":t}))

# ── MANUFACTURING (20) ──────────────────────────────────────────────────────
for mean,sigma,usl,lsl,cp in [(100,1,106,94,1.0),(50,0.5,53,47,1.0),(200,2,212,188,1.0),(10,0.1,10.6,9.4,1.0)]:
    SEEDS.append(("manufacturing", {"operation":"process_capability","process_mean":mean,"process_sigma":sigma,"usl":usl,"lsl":lsl,"claimed_cp":cp}))
for mean,sigma,usl,lsl,sl in [(100,1,106,94,6.0),(50,0.5,53,47,6.0),(200,2,212,188,6.0),(10,0.1,10.6,9.4,6.0)]:
    SEEDS.append(("manufacturing", {"operation":"sigma_level","mean":mean,"sigma":sigma,"usl":usl,"lsl":lsl,"claimed_sigma":sl}))
for mean,sigma,k,ucl,lcl in [(100,1,3,103,97),(50,0.5,3,51.5,48.5),(200,2,3,206,194),(20,0.2,3,20.6,19.4)]:
    SEEDS.append(("manufacturing", {"operation":"spc_control_limits","process_mean":mean,"process_sigma":sigma,"k":k,"claimed_ucl":ucl,"claimed_lcl":lcl}))
for dims,rss in [([0.1,0.1,0.1],0.173),([0.05,0.05],0.071),([0.2,0.1,0.1],0.245),([0.5,0.3,0.4],0.707)]:
    SEEDS.append(("manufacturing", {"operation":"tolerance_stack_rss","dimensions":dims,"claimed_rss":rss}))
for mean2,sigma2,dpmo in [(0,1,2700),(0,1,63),(0,1,3.4)]:
    SEEDS.append(("manufacturing", {"operation":"sigma_level","mean":100,"sigma":1,"usl":103,"lsl":97,"claimed_sigma":3.0}))

# ── MATHEMATICS (30) ─────────────────────────────────────────────────────────
equalities = [
    ("2**10","1024"),("sin(pi/2)","1"),("cos(0)","1"),("log(E)","1"),("sqrt(144)","12"),
    ("factorial(5)","120"),("2**8","256"),("3**4","81"),("10**3","1000"),("5**3","125"),
]
for a,b in equalities:
    SEEDS.append(("mathematics", "equality", {"expr_a":a,"expr_b":b}))
derivatives = [
    ("x**2","x","2*x"),("x**3","x","3*x**2"),("sin(x)","x","cos(x)"),
    ("cos(x)","x","-sin(x)"),("exp(x)","x","exp(x)"),
    ("ln(x)","x","1/x"),("x**4","x","4*x**3"),("sqrt(x)","x","1/(2*sqrt(x))"),
]
for fn,var,d in derivatives:
    SEEDS.append(("mathematics", "derivative", {"function":fn,"variable":var,"claimed_derivative":d}))
integrals = [
    ("x","x","x**2/2"),("x**2","x","x**3/3"),("cos(x)","x","sin(x)"),
    ("sin(x)","x","-cos(x)"),("exp(x)","x","exp(x)"),("1/x","x","ln(x)"),
    ("2*x","x","x**2"),("x**3","x","x**4/4"),
]
for fn,var,antideriv in integrals:
    SEEDS.append(("mathematics", "integral", {"integrand":fn,"variable":var,"claimed_antiderivative":antideriv}))

# ── MEDICINE (30) ────────────────────────────────────────────────────────────
for wt,ht,bmi,cls in [
    (70,1.75,22.9,"normal"),(90,1.75,29.4,"overweight"),(110,1.75,35.9,"obese"),
    (55,1.65,20.2,"normal"),(45,1.60,17.6,"underweight"),(120,1.70,41.5,"obese"),
    (80,1.80,24.7,"normal"),(100,1.80,30.9,"obese"),(60,1.70,20.8,"normal"),
]:
    SEEDS.append(("medicine", {"operation":"bmi","weight_kg":wt,"height_m":ht,"claimed_bmi":bmi,"claimed_classification":cls}))
for sys,dia,cls2 in [
    (120,80,"normal"),(130,85,"elevated"),(145,95,"stage1"),(165,105,"stage2"),
    (90,60,"low"),(110,70,"normal"),(125,82,"elevated"),(155,100,"stage2"),
]:
    SEEDS.append(("medicine", {"operation":"blood_pressure","systolic":sys,"diastolic":dia,"claimed_classification":cls2}))
for a1c,cls3 in [(5.6,"normal"),(6.0,"prediabetic"),(7.5,"diabetic"),(5.0,"normal"),(8.5,"diabetic"),(6.4,"prediabetic")]:
    SEEDS.append(("medicine", {"operation":"a1c","a1c_pct":a1c,"claimed_classification":cls3}))
for wt2,ht2,age,sex,egfr in [(70,1.75,50,"M",88),(80,1.70,65,"M",62),(55,1.60,45,"F",90),(90,1.80,70,"M",55)]:
    SEEDS.append(("medicine", {"operation":"egfr_cockcroft","weight_kg":wt2,"height_m":ht2,"age_years":age,"sex":sex,"serum_creatinine":1.0,"claimed_egfr":egfr}))
for sys2,dia2,map2 in [(120,80,93),(130,85,100),(140,90,107),(110,70,83)]:
    SEEDS.append(("medicine", {"operation":"map","systolic":sys2,"diastolic":dia2,"claimed_map":map2}))

# ── METEOROLOGY (20) ─────────────────────────────────────────────────────────
for tf,rh,hi in [(85,60,90),(95,70,108),(100,80,127),(75,50,75),(90,50,94)]:
    SEEDS.append(("meteorology", {"operation":"heat_index","temperature_f":tf,"relative_humidity_pct":rh,"claimed_heat_index_f":hi}))
for tf2,ws,wc in [(30,20,22),(20,15,8),(10,25,-1),(0,30,-14),(40,10,34)]:
    SEEDS.append(("meteorology", {"operation":"wind_chill","temperature_f":tf2,"wind_speed_mph":ws,"claimed_wind_chill_f":wc}))
for tc,rh2,dp in [(25,60,16.9),(30,70,24.0),(20,50,9.3),(35,80,31.2),(15,40,1.9)]:
    SEEDS.append(("meteorology", {"operation":"dew_point","temperature_c":tc,"relative_humidity_pct":rh2,"claimed_dew_point_c":dp}))
for tc2,svp in [(0,0.611),(20,2.338),(100,101.325),(25,3.169),(30,4.243)]:
    SEEDS.append(("meteorology", {"operation":"saturation_vapor_pressure","temperature_c":tc2,"claimed_svp_kPa":svp}))

# ── MUSIC_THEORY (20) ────────────────────────────────────────────────────────
intervals = [
    ("C","G","P5",7),("C","E","M3",4),("C","D","M2",2),("C","A","M6",9),("C","B","M7",11),
    ("A","E","P5",7),("D","A","P5",7),("G","D","P5",7),("E","B","P5",7),("F","C","P5",7),
]
for n1,n2,iname,semi in intervals:
    SEEDS.append(("music_theory", {"operation":"interval_semitones","note1":n1,"note2":n2,"claimed_interval_name":iname,"claimed_semitones":semi}))
for midi,freq in [(69,440.0),(60,261.63),(72,523.25),(57,220.0),(81,880.0)]:
    SEEDS.append(("music_theory", {"operation":"equal_temperament_freq","midi_note":midi,"claimed_freq_hz":freq}))
for note,key,mode,mem in [("C","C","major",True),("D","C","major",True),("F#","G","major",True),("Bb","F","major",True),("E","A","minor",True)]:
    SEEDS.append(("music_theory", {"operation":"scale_membership","note":note,"key":key,"mode":mode,"claimed_member":mem}))
for fa,fb,ratio in [(440,880,2.0),(440,660,1.5),(440,554,1.26),(261.63,329.63,1.26)]:
    SEEDS.append(("music_theory", {"operation":"frequency_ratio","freq_a":fa,"freq_b":fb,"claimed_ratio":ratio}))

# ── NETWORKING (30) ──────────────────────────────────────────────────────────
for ip,cidr,contains in [
    ("192.168.1.100","192.168.1.0/24",True),("10.0.0.50","10.0.0.0/8",True),
    ("172.16.5.1","172.16.0.0/12",True),("8.8.8.8","8.8.0.0/16",True),
    ("192.168.2.1","192.168.1.0/24",False),("10.1.0.1","10.0.0.0/24",False),
    ("172.32.0.1","172.16.0.0/12",False),("8.8.4.4","8.8.8.0/24",False),
]:
    SEEDS.append(("networking", {"operation":"cidr_membership","ip_to_check":ip,"cidr":cidr,"claimed_member":contains}))
for ip2,ok in [
    ("192.168.1.1",True),("10.0.0.1",True),("256.1.1.1",False),("0.0.0.0",True),
    ("255.255.255.255",True),("8.8.8.8",True),("::1",False),("abc",False),
]:
    SEEDS.append(("networking", {"operation":"ip_format","address":ip2,"claimed_valid_ipv4":ok}))
for mac,ok2 in [
    ("00:1A:2B:3C:4D:5E",True),("FF:FF:FF:FF:FF:FF",True),("00-1A-2B-3C-4D-5E",True),
    ("00:1A:2B:3C:4D",False),("GG:1A:2B:3C:4D:5E",False),
]:
    SEEDS.append(("networking", {"operation":"mac_format","mac":mac,"claimed_valid":ok2}))
for prefix,hosts in [(24,254),(16,65534),(8,16777214),(25,126),(28,14),(29,6),(30,2),(27,30)]:
    SEEDS.append(("networking", {"operation":"subnet_host_count","subnet_prefix":prefix,"claimed_hosts":hosts}))
for ip3,cidr2 in [("172.16.100.5","172.16.0.0/12"),("192.168.0.1","192.168.0.0/16")]:
    SEEDS.append(("networking", {"operation":"cidr_membership","ip_to_check":ip3,"cidr":cidr2,"claimed_member":True}))

# ── NUMBER_THEORY (13) ──────────────────────────────────────────────────────
for n,p in [(2,True),(3,True),(4,False),(17,True),(97,True),(100,False),(7,True),(15,False),(23,True),(1,False),(51,False),(113,True),(1000003,True)]:
    SEEDS.append(("number_theory", {"operation":"prime_check","n":n,"claimed_prime":p}))

# ── NUTRITION (20) ──────────────────────────────────────────────────────────
for wt,ht2,cls in [
    (70,1.75,"normal"),(90,1.75,"overweight"),(50,1.65,"normal"),(110,1.70,"obese"),(60,1.60,"normal"),
    (45,1.55,"underweight"),(80,1.80,"normal"),(100,1.70,"obese"),(55,1.70,"normal"),(75,1.65,"normal"),
]:
    SEEDS.append(("nutrition", {"operation":"bmi_classification","weight_kg":wt,"height_m":ht2}))
for c,pr,fat,carb,ok in [
    (2000,150,67,250,True),(2500,188,83,313,True),(1800,135,60,225,True),(2200,165,73,275,True),
    (3000,225,100,375,True),(1500,113,50,188,True),(2400,180,80,300,True),(1600,120,53,200,True),
]:
    SEEDS.append(("nutrition", {"operation":"macronutrient_calories","carb_g":carb,"protein_g":pr,"fat_g":fat,"alcohol_g":0,"claimed_calories":c}))
for nut,intake,rda,ok in [
    ("vitamin_c",60,90,False),("iron",18,18,True),("calcium",1000,1000,True),("vitamin_d",600,600,True),
]:
    SEEDS.append(("nutrition", {"operation":"rda_compliance","nutrient":nut,"intake_mg":intake,"rda_mg":rda,"claimed_compliant":ok}))

# ── OPTICS (20) ──────────────────────────────────────────────────────────────
for n1,n2,t1,t2 in [
    (1.0,1.5,30,19.47),(1.5,1.0,19.47,30),(1.0,1.33,45,32.1),(1.33,1.5,30,26.38),(1.0,2.4,20,8.2),
    (1.0,1.5,45,28.13),(1.5,2.4,20,12.3),(1.0,1.33,30,22.0),(1.0,1.5,60,35.26),(1.5,1.0,40,74.6),
]:
    SEEDS.append(("optics", {"operation":"snell_law","n1":n1,"n2":n2,"theta1_deg":t1,"claimed_theta2_deg":t2}))
for f,do,di in [(0.1,0.3,0.15),(0.2,0.6,0.3),(0.05,0.2,0.067),(0.5,2.0,1.0),(0.25,1.0,0.5)]:
    SEEDS.append(("optics", {"operation":"thin_lens","focal_length_m":f,"object_distance_m":do,"claimed_image_distance_m":di}))
for wl,D,res in [(550e-9,0.05,1.34e-5),(500e-9,0.1,6.1e-6),(700e-9,0.02,4.27e-5)]:
    SEEDS.append(("optics", {"operation":"rayleigh_diffraction","wavelength_m":wl,"aperture_diameter_m":D,"claimed_resolution_rad":res}))
for f2,obj2,mag in [(0.1,0.3,0.5),(0.2,0.6,0.5),(0.5,2.0,0.5)]:
    SEEDS.append(("optics", {"operation":"magnification","focal_length_m":f2,"object_distance_m":obj2,"claimed_magnification":mag}))

# ── PHOTOGRAPHY (20) ─────────────────────────────────────────────────────────
evs = [(1.4,"1/500",100,8),(2.8,"1/125",100,8),(4.0,"1/60",100,8),(8.0,"1/30",100,8),
       (1.4,"1/125",400,9),(2.8,"1/60",400,9),(1.4,"1/250",200,8),(5.6,"1/30",200,9)]
for f,s,iso,ev in evs:
    SEEDS.append(("photography", {"operation":"exposure_value","f_number":f,"shutter_seconds":eval(s.replace("1/","1/").replace("1/","1.0/")),"iso":iso,"claimed_ev":ev}))
for fl,sensor,aov in [(50,35.0,39.6),(24,35.0,73.7),(85,35.0,23.9),(35,35.0,54.4),(100,35.0,20.4)]:
    SEEDS.append(("photography", {"operation":"angle_of_view","focal_length_mm":fl,"sensor_dimension_mm":sensor,"claimed_aov_degrees":aov}))
for fl2,fn2,coc,hfd in [(50,8,0.03,10417),(24,8,0.03,2400),(85,5.6,0.03,17024),(35,11,0.03,3636)]:
    SEEDS.append(("photography", {"operation":"hyperfocal_distance","focal_length_mm":fl2,"f_number":fn2,"circle_of_confusion_mm":coc,"claimed_hyperfocal_m":hfd}))
for set_a,set_b,equiv in [
    ({"f":2.8,"s":"1/500","iso":100},{"f":5.6,"s":"1/125","iso":100},True),
    ({"f":1.4,"s":"1/1000","iso":100},{"f":2.8,"s":"1/250","iso":100},True),
    ({"f":4.0,"s":"1/250","iso":200},{"f":8.0,"s":"1/125","iso":200},True),
]:
    SEEDS.append(("photography", {"operation":"reciprocity_equivalent","settings_a":set_a,"settings_b":set_b,"claimed_equivalent":equiv}))

# ── QUANTUM_COMPUTING (18) ──────────────────────────────────────────────────
for amps,norm in [
    ([0.7071,0.7071],True),([1.0,0.0],True),([0.0,1.0],True),([0.5,0.866],True),([0.6,0.8],True),([0.5,0.5,0.5,0.5],True),
]:
    s = sum(a**2 for a in amps)
    SEEDS.append(("quantum_computing", {"operation":"qubit_normalization","amplitudes":amps,"claimed_normalized":norm}))
for n,grover_iters in [(4,1),(16,3),(64,6),(256,12),(1024,25),(8,2),(32,4)]:
    SEEDS.append(("quantum_computing", {"operation":"grover_iterations","n_items":n,"claimed_iterations":grover_iters}))
for eigs,ent in [([1.0,0.0],0.0),([0.5,0.5],1.0),([0.7,0.3],0.881),([0.25,0.25,0.25,0.25],2.0)]:
    SEEDS.append(("quantum_computing", {"operation":"von_neumann_entropy","density_eigenvalues":eigs,"claimed_entropy":ent}))
for qber,secure in [(0.05,True),(0.11,False),(0.02,True),(0.15,False),(0.08,True)]:
    SEEDS.append(("quantum_computing", {"operation":"bb84","qber":qber,"claimed_secure":secure}))

# ── REAL_ESTATE (30) ─────────────────────────────────────────────────────────
for p,r,y,monthly in [
    (300000,0.065,30,1896.20),(400000,0.055,30,2271.16),(500000,0.07,30,3326.51),
    (200000,0.06,15,1687.71),(250000,0.05,20,1649.89),(350000,0.075,25,2573.56),
    (100000,0.045,30,506.69),(450000,0.065,30,2843.26),(600000,0.06,30,3597.30),
]:
    SEEDS.append(("real_estate", {"operation":"monthly_mortgage","loan_amount":p,"annual_rate":r,"loan_term_months":y*12,"claimed_monthly_payment":monthly}))
for noi,pv,cr in [(24000,300000,0.08),(36000,400000,0.09),(18000,200000,0.09),(50000,500000,0.10),(30000,375000,0.08)]:
    SEEDS.append(("real_estate", {"operation":"cap_rate","net_operating_income":noi,"property_value":pv,"claimed_cap_rate":cr}))
for pv2,rent,grm in [(300000,24000,12.5),(400000,32000,12.5),(500000,50000,10.0),(200000,20000,10.0),(350000,28000,12.5)]:
    SEEDS.append(("real_estate", {"operation":"gross_rent_multiplier","property_value":pv2,"annual_gross_rent":rent,"claimed_grm":grm}))
for loan,pv3,ltv in [(240000,300000,0.80),(320000,400000,0.80),(180000,200000,0.90),(350000,500000,0.70),(280000,350000,0.80)]:
    SEEDS.append(("real_estate", {"operation":"loan_to_value","loan_amount":loan,"property_value":pv3,"claimed_ltv":ltv}))
for noi2,ads,dscr in [(36000,24000,1.50),(50000,40000,1.25),(60000,40000,1.50),(30000,25000,1.20),(80000,50000,1.60)]:
    SEEDS.append(("real_estate", {"operation":"dscr","net_operating_income":noi2,"annual_debt_service":ads,"claimed_dscr":dscr}))
for rent2,pv4,ry in [(18000,250000,0.072),(24000,300000,0.08),(30000,400000,0.075),(15000,200000,0.075)]:
    SEEDS.append(("real_estate", {"operation":"rental_yield","annual_gross_rent":rent2,"property_value":pv4,"claimed_yield":ry}))

# ── SCRIPTURE_ANCHORS (15) ──────────────────────────────────────────────────
refs = [
    ("John 3:16","For God so loved the world that he gave his one and only Son"),
    ("Romans 8:28","And we know that in all things God works for the good"),
    ("Philippians 4:13","I can do all things through Christ who strengthens me"),
    ("Proverbs 3:5","Trust in the Lord with all your heart"),
    ("Matthew 5:3","Blessed are the poor in spirit for theirs is the kingdom of heaven"),
    ("Isaiah 40:31","Those who hope in the Lord will renew their strength"),
    ("Psalm 23:1","The Lord is my shepherd I shall not want"),
    ("1 Corinthians 13:4","Love is patient love is kind"),
    ("Joshua 1:9","Be strong and courageous do not be afraid"),
    ("Jeremiah 29:11","For I know the plans I have for you"),
    ("Ephesians 2:8","For it is by grace you have been saved through faith"),
    ("Romans 12:2","Do not conform to the pattern of this world"),
    ("Galatians 5:22","But the fruit of the Spirit is love joy peace"),
    ("Hebrews 11:1","Now faith is confidence in what we hope for"),
    ("Revelation 21:4","He will wipe every tear from their eyes"),
]
for ref,txt in refs:
    SEEDS.append(("scripture_anchors", [{"reference":ref,"text":txt}]))

# ── SOIL_SCIENCE (30) ────────────────────────────────────────────────────────
crops_ph = [
    ("tomato",6.5,"suitable"),("blueberry",5.0,"suitable"),("wheat",6.0,"suitable"),
    ("potato",5.5,"suitable"),("alfalfa",7.0,"suitable"),("corn",6.2,"suitable"),
    ("rice",5.5,"suitable"),("soybean",6.5,"suitable"),("strawberry",6.0,"suitable"),
    ("spinach",7.0,"suitable"),("carrot",6.5,"suitable"),("lettuce",6.5,"suitable"),
]
for crop,ph,suit in crops_ph:
    SEEDS.append(("soil_science", {"operation":"ph_suitability","crop":crop,"soil_ph":ph,"claimed_suitability":suit}))
textures = [
    (40,40,20,"loam"),(70,20,10,"sandy_loam"),(10,70,20,"silt_loam"),(20,20,60,"clay"),
    (50,30,20,"sandy_clay_loam"),(30,50,20,"silt_loam"),(60,30,10,"sandy_loam"),(15,60,25,"silty_clay_loam"),
]
for sand,silt,clay,cls in textures:
    SEEDS.append(("soil_science", {"operation":"soil_texture","sand_pct":sand,"silt_pct":silt,"clay_pct":clay,"claimed_class":cls}))
for crop2,npk in [("corn","N:180,P:80,K:100"),("wheat","N:120,P:60,K:80"),("rice","N:100,P:50,K:60"),("soybean","N:20,P:60,K:80")]:
    SEEDS.append(("soil_science", {"operation":"npk_requirement","crop":crop2,"claimed_npk":npk}))
for cur,tgt,buf,area,lime in [(5.5,6.5,6.0,1,2.5),(5.0,6.5,6.0,1,5.0),(6.0,7.0,6.5,1,1.5),(4.5,6.5,5.5,1,7.5),(5.8,6.5,6.2,1,1.0)]:
    SEEDS.append(("soil_science", {"operation":"lime_requirement","soil_ph":cur,"target_ph":tgt,"buffer_ph":buf,"area_hectares":area,"claimed_lime_t_ha":lime}))
for crop3,eto,stage,etc in [("wheat",5.0,"mid",6.0),("corn",6.0,"mid",7.2),("tomato",5.5,"late",4.4),("rice",5.0,"initial",2.5)]:
    SEEDS.append(("soil_science", {"operation":"irrigation_req","crop":crop3,"eto_mm_day":eto,"growth_stage":stage,"claimed_etc":etc}))

# ── SPORTS_ANALYTICS (20) ───────────────────────────────────────────────────
for wins,losses,rs,ra,exp in [
    (95,67,800,650,0.602),(85,77,700,700,0.500),(110,52,900,600,0.692),
    (70,92,600,750,0.390),(100,62,850,680,0.609),(75,87,650,730,0.442),
]:
    SEEDS.append(("sports_analytics", {"operation":"pythagorean_expectation","team_wins":wins,"team_losses":losses,"runs_scored":rs,"runs_allowed":ra,"claimed_expectation":exp}))
for ea,eb,k,exp_a in [(1500,1500,32,0.5),(1600,1400,32,0.76),(1700,1300,32,0.91),(1800,1200,32,0.97),(1550,1450,32,0.64)]:
    SEEDS.append(("sports_analytics", {"operation":"elo_expected_score","elo_a":ea,"elo_b":eb,"elo_K":k,"claimed_expected_a":exp_a}))
for w,l,fw,fl,gb in [(95,67,100,62,5.0),(85,77,95,67,10.0),(75,87,100,62,20.5),(70,92,95,67,24.5)]:
    SEEDS.append(("sports_analytics", {"operation":"games_behind","team_wins":w,"team_losses":l,"first_wins":fw,"first_losses":fl,"claimed_gb":gb}))
for ea2,eb2,result,k2,new_ea in [(1500,1500,1.0,32,1516),(1500,1500,0.0,32,1484),(1600,1400,1.0,32,1608),(1400,1600,1.0,32,1424)]:
    SEEDS.append(("sports_analytics", {"operation":"elo_rating_update","elo_a":ea2,"elo_b":eb2,"result_a":result,"elo_K":k2,"claimed_new_elo_a":new_ea}))
for h,ab,avg in [(85,300,0.283),(120,400,0.300),(50,200,0.250),(180,600,0.300),(70,250,0.280)]:
    SEEDS.append(("sports_analytics", {"operation":"batting_average","hits":h,"at_bats":ab,"claimed_avg":avg}))

# ── STATISTICS (15) ─────────────────────────────────────────────────────────
for mean,lo,hi in [(50,45.1,54.9),(100,95.0,105.0),(0,- 1.96,1.96),(75,70,80),(200,192,208)]:
    SEEDS.append(("statistics_confidence_interval", {"estimate":mean,"ci_low":lo,"ci_high":hi}))
for ps,method,alpha in [
    ([0.04,0.03,0.02,0.05],"bonferroni",0.05),
    ([0.001,0.04,0.08,0.2],"fdr_bh",0.05),
    ([0.01,0.02,0.03],"bonferroni",0.05),
    ([0.1,0.2,0.3,0.4,0.5],"fdr_bh",0.05),
    ([0.001,0.001,0.5],"bonferroni",0.05),
]:
    SEEDS.append(("statistics_multiple_comparisons", {"raw_p_values":ps,"method":method,"alpha":alpha}))
for obs,exp2,test in [
    ([15,25,20,30,10],[20,20,20,20,20],"chi_square"),
    ([30,20],[25,25],"chi_square"),
    ([10,10,10],[10,10,10],"chi_square"),
    ([40,60],[50,50],"chi_square"),
    ([5.1,5.4,5.0],[4.8,4.7,5.1],"t_test"),
]:
    SEEDS.append(("statistics_pvalue", {"observed":obs,"expected":exp2,"test":test}))

# ── WITNESS (25) ─────────────────────────────────────────────────────────────
claims = [
    "Water boils at 100 degrees Celsius at standard atmospheric pressure.",
    "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
    "The human body has 206 bones in adulthood.",
    "DNA carries genetic information in sequences of four bases: A, T, C, G.",
    "The sum of angles in a triangle is 180 degrees.",
    "E = mc^2 is Einstein's mass-energy equivalence formula.",
    "Photosynthesis converts CO2 and water into glucose and oxygen.",
    "The atomic number of carbon is 6.",
    "The Earth completes one orbit of the Sun in approximately 365.25 days.",
    "Gravity on Earth's surface is approximately 9.81 m/s^2.",
    "The first law of thermodynamics states energy cannot be created or destroyed.",
    "Pi is approximately 3.14159265358979.",
    "Hydrogen has atomic number 1 and is the lightest element.",
    "The mitochondria is the powerhouse of the cell.",
    "Newton's second law: F = ma.",
    "The pH of pure water at 25°C is 7.",
    "Sound travels at approximately 343 m/s in air at 20°C.",
    "The human genome contains approximately 3 billion base pairs.",
    "Avogadro's number is 6.022 × 10^23 particles per mole.",
    "Ohm's law: V = IR.",
    "The Bible was written across 1500 years by 40 authors.",
    "Israel became a modern nation in 1948.",
    "The Dead Sea Scrolls were discovered in 1947.",
    "The Sermon on the Mount is found in Matthew 5-7.",
    "Acts 2 records the first Pentecost of the early church.",
]
for c in claims:
    SEEDS.append(("witness", {"claim":c,"sources":["encyclopedic"]}))

print(f"Total seeds prepared: {len(SEEDS)}")


def _run_one(row):
    """Dispatch one seed row → (domain, spec, result)."""
    domain = row[0]

    if domain == "governance_decision_packet":
        # row: (domain, decision, rationale, alternatives, witness_count)
        _, dec, rat, alts, wc = row
        fn = ALL_TOOLS["verify_governance_decision_packet"]
        packet = {"decision": dec, "rationale": rat, "alternatives_considered": alts}
        spec = packet
        result = fn(packet, witness_count=wc)

    elif domain == "mathematics":
        # row: (domain, mode, params_dict)
        _, mode, params = row
        fn = ALL_TOOLS["verify_mathematics"]
        spec = {"mode": mode, **params}
        result = fn(mode, params)

    elif domain == "scripture_anchors":
        # row: (domain, anchors_list)
        _, anchors = row
        fn = ALL_TOOLS["verify_scripture_anchors"]
        spec = {"anchors": anchors}
        result = fn(anchors)

    elif domain in ("statistics_confidence_interval", "statistics_multiple_comparisons", "statistics_pvalue"):
        _, spec = row
        fn = ALL_TOOLS[f"verify_{domain}"]
        if domain == "statistics_confidence_interval":
            result = fn(spec["estimate"], spec["ci_low"], spec["ci_high"])
        elif domain == "statistics_multiple_comparisons":
            result = fn(spec["raw_p_values"], spec["method"], spec.get("alpha", 0.05))
        else:
            result = fn(spec)

    else:
        # Standard: (domain, spec_dict)
        _, spec = row
        fn = ALL_TOOLS.get(f"verify_{domain}")
        if fn is None:
            return domain, None, None, "NO_TOOL"
        result = fn(spec)

    entry = store.append(domain, spec, result)
    summary = entry.get("summary", "UNKNOWN")
    record_confirmation(domain, spec, IID, summary=summary, entry_id=entry.get("id"))
    return domain, spec, result, summary


def main():
    t0 = time.time()
    counts = {"ok": 0, "error": 0, "no_tool": 0}
    summaries = {}

    for idx, row in enumerate(SEEDS, 1):
        try:
            domain, spec, result, summary = _run_one(row)
            if summary == "NO_TOOL":
                counts["no_tool"] += 1
                print(f"  [{idx:04d}] ~ {domain:<35} (no tool)")
            else:
                counts["ok"] += 1
                summaries[domain] = summaries.get(domain, 0) + 1
                marker = "+" if summary == "CONFIRMED" else ("." if summary == "NOT_APPLICABLE" else "!")
                if idx % 50 == 0 or summary == "CONFIRMED":
                    print(f"  [{idx:04d}] {marker} {domain:<35} {summary}")
        except Exception as exc:
            counts["error"] += 1
            print(f"  [{idx:04d}] ! {row[0]:<35} {str(exc)[:60]}")

    elapsed = time.time() - t0
    from api.trust_index import trust_stats
    stats = trust_stats()
    total_hashes = sum(v.get("total_hashes", 0) for v in stats.values())

    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.1f}s")
    print(f"  Stored:   {counts['ok']}")
    print(f"  Errors:   {counts['error']}")
    print(f"  No tool:  {counts['no_tool']}")
    print(f"\nVault: {len(stats)} domains, {total_hashes} total hashes")
    print(f"Seeds per domain:")
    for d, n in sorted(summaries.items()):
        print(f"  {d:<40} {n}")


if __name__ == "__main__":
    main()
