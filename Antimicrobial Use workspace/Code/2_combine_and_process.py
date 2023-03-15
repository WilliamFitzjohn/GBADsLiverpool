#%% About
'''
'''
#%% Functions

# Translate a PERT distribution to the equivalent Beta
# Output a dataframe with samples generated from the distribution and a histogram
# Usage: pert_samples = generate_pert(10000, 1, 8, 10)
def generate_pert(N_SAMPLES ,MIN ,MODE ,MAX ,LAMBDA=4):
    funcname = inspect.currentframe().f_code.co_name

    mean = (MIN + (LAMBDA * MODE) + MAX) / (LAMBDA + 2)
    alpha = (mean - MIN) * (2*MODE - MIN - MAX) / ((MODE - mean) * (MAX - MIN))
    beta = alpha * (MAX - mean) / (mean - MIN)

    print(f"<{funcname}> PERT distribution: ({MIN}, {MODE}, {MAX}) with lambda={LAMBDA}")
    print(f"<{funcname}> Equivalent Beta distribution: {alpha=:.3f}, {beta=:.3f}")

    # Generate samples
    beta_distr = sps.beta(alpha ,beta)
    generated_df = pd.DataFrame(index=range(N_SAMPLES))
    generated_df['rand_beta'] = beta_distr.rvs(size=generated_df.shape[0])      # Generate random numbers from Beta distribution (on scale 0,1)
    generated_df['rand_pert'] = (generated_df['rand_beta'] * (MAX - MIN)) + MIN   # Translate from (0,1) to scale of PERT

    # Plot
    snplt = sns.displot(
    	data=generated_df
    	,x='rand_pert'
    	,kind='hist'
        ,stat='probability'
        ,bins=20
    )
    plt.title(f"PERT({MIN}, {MODE}, {MAX}) with lambda={LAMBDA}\n Recreated as Beta({alpha:.2f}, {beta:.2f})\n {N_SAMPLES:,} samples")

    return generated_df

pert_samples = generate_pert(10000, 1, 8, 10)

# Translate a PERT distribution to the equivalent Beta
# Output the beta distribution object for further processing
def pert_to_beta(MIN ,MODE ,MAX ,LAMBDA=4):
    funcname = inspect.currentframe().f_code.co_name

    mean = (MIN + (LAMBDA * MODE) + MAX) / (LAMBDA + 2)
    alpha = (mean - MIN) * (2*MODE - MIN - MAX) / ((MODE - mean) * (MAX - MIN))
    beta = alpha * (MAX - mean) / (mean - MIN)
    beta_distr = sps.beta(alpha ,beta)

    print(f"<{funcname}> PERT distribution: ({MIN}, {MODE}, {MAX}) with lambda={LAMBDA}")
    print(f"<{funcname}> Equivalent Beta distribution: {alpha=:.3f}, {beta=:.3f}")

    return beta_distr

beta_distr = pert_to_beta(1, 8, 10)

# Endpoints of the range that contains alpha percent of the distribution
beta_distr_ci95 = beta_distr.interval(0.95)
pert_distr_ci95_low = (beta_distr_ci95[0] * (10 - 1)) + 1   # Translate from (0,1) to scale of PERT
pert_distr_ci95_high = (beta_distr_ci95[1] * (10 - 1)) + 1   # Translate from (0,1) to scale of PERT

#%% Structure: one row per region & antimicrobial

# =============================================================================
#### Prepare AM usage
# =============================================================================
amu2018_m_tomerge = amu2018_m.copy()

# =============================================================================
#### Combine AM usage and importance
# =============================================================================
# Modify antimicrobial names in importance data to match
amu_importance_tomerge = amu_importance.copy()

# Remove special characters from class names
amu_importance_tomerge['antimicrobial_class'] = amu_importance_tomerge['antimicrobial_class'].str.lower() \
   .str.strip().str.replace(' ' ,'_' ,regex=False) \
   .str.replace('/' ,'_' ,regex=False).str.replace('\\' ,'_' ,regex=False) \
   .str.replace('(' ,'_' ,regex=False).str.replace(')' ,'_' ,regex=False) \
   .str.replace('-' ,'_' ,regex=False).str.replace('+' ,'_' ,regex=False) \
   .str.replace('.' ,'_' ,regex=False).str.replace(',' ,'_' ,regex=False) \

# Recode classes to match AMU data
recode_classes = {
    'cephalosporins__all_generations_':'cephalosporins__all_generations'
    ,'sulfonamids':'sulfonamides__including_trimethoprim'
    }
amu_importance_tomerge['antimicrobial_class'] = amu_importance_tomerge['antimicrobial_class'].replace(recode_classes)

datainfo(amu_importance_tomerge)

# Merge with AMU
amu2018_combined_tall = pd.merge(
    left=amu2018_m_tomerge.query("antimicrobial_class != 'total_antimicrobials'").query("region != 'Global'")
    ,right=amu_importance_tomerge[['antimicrobial_class' ,'who_importance_ctg' ,'woah_importance_ctg' ,'onehealth_importance_ctg']]
    ,on='antimicrobial_class'
    ,how='left'
)

# Fill missing importance with "Unknown"
amu2018_combined_tall['who_importance_ctg'] = amu2018_combined_tall['who_importance_ctg'].fillna('D: Unknown')
amu2018_combined_tall['woah_importance_ctg'] = amu2018_combined_tall['woah_importance_ctg'].fillna('D: Unknown')
amu2018_combined_tall['onehealth_importance_ctg'] = amu2018_combined_tall['onehealth_importance_ctg'].fillna('Unknown')

# =============================================================================
#### Create antimicrobial class groupings
# =============================================================================
# Group the AM classes that individually make up less than 2% of the global total usage
# Groupings must still respect importance categories
amu_total_byclass = amu2018_m_tomerge.query("antimicrobial_class != 'total_antimicrobials'").query("region == 'Global'").query("scope == 'All'")
amu_total_byclass['usage_rank_lowis1'] = amu_total_byclass['amu_tonnes'].rank()
amu_total_byclass['usage_rank_highis1'] = amu_total_byclass['amu_tonnes'].rank(ascending=False)

global_total_amu_tonnes = amu_total_byclass['amu_tonnes'].sum()
low_volume_classes = list(amu_total_byclass.query(f"amu_tonnes < {global_total_amu_tonnes} * 0.02")['antimicrobial_class'])

def define_class_group(INPUT_ROW):
	if INPUT_ROW['antimicrobial_class'] in low_volume_classes:
		if 'Important' in INPUT_ROW['onehealth_importance_ctg']:
			OUTPUT = 'other_important'
		else:
			OUTPUT = 'other'
	else:
		OUTPUT = INPUT_ROW['antimicrobial_class']
	return OUTPUT
amu2018_combined_tall['antimicrobial_class_group'] = amu2018_combined_tall.apply(define_class_group ,axis=1)

# Further grouping: top 3 classes by global usage vs. everything else
# Regardless of importance category
top3_globally = list(amu_total_byclass.query(f"usage_rank_highis1 <= 3 ")['antimicrobial_class'])
amu2018_combined_tall['antimicrobial_class_group2'] = 'others'
amu2018_combined_tall.loc[amu2018_combined_tall['antimicrobial_class'].isin(top3_globally) ,'antimicrobial_class_group2'] = \
    amu2018_combined_tall['antimicrobial_class']

# =============================================================================
#### Add biomass data
# =============================================================================
# Merge
amu2018_combined_tall = pd.merge(
    left=amu2018_combined_tall
    ,right=amu2018_biomass.query("segment == 'Countries reporting AMU data'")[['region' ,'biomass_total_kg' ,'biomass_total_terr_kg']]
    ,on='region'
    ,how='left'
)

# Apply appropriate biomass to each row based on scope
def biomass_for_scope(INPUT_ROW):
    if INPUT_ROW['scope'].upper() == 'ALL':
        OUTPUT = INPUT_ROW['biomass_total_kg']
    elif INPUT_ROW['scope'].upper() == 'TERRESTRIAL FOOD PRODUCING':
        OUTPUT = INPUT_ROW['biomass_total_terr_kg']
    else:
        OUTPUT = np.nan
    return OUTPUT
amu2018_combined_tall['biomass_total_kg'] = amu2018_combined_tall.apply(biomass_for_scope ,axis=1)
del amu2018_combined_tall['biomass_total_terr_kg']

# Calculate AMU per kg biomass
amu2018_combined_tall['amu_mg_perkgbiomass'] = (amu2018_combined_tall['amu_tonnes'] / amu2018_combined_tall['biomass_total_kg']) * 1e9

# =============================================================================
#### Export
# =============================================================================
datainfo(amu2018_combined_tall)

amu2018_combined_tall.to_csv(os.path.join(PRODATA_FOLDER ,'amu2018_combined_tall.csv') ,index=False)
amu2018_combined_tall.to_csv(os.path.join(DASH_DATA_FOLDER ,'amu2018_combined_tall.csv') ,index=False)

#%% Structure: one row per region

# =============================================================================
#### Combine biomass and AM usage
# =============================================================================
# Pivot Biomass to get countries reporting and total region into columns
# Keep total biomass and terrestrial biomass
amu2018_biomass_p = amu2018_biomass.query("region != 'Global'").pivot(
    index='region'
    ,columns='segment'
    ,values=['biomass_total_kg' ,'biomass_total_terr_kg']
)
amu2018_biomass_p = colnames_from_index(amu2018_biomass_p) 	# If multi-indexed columns were created, flatten index
cleancolnames(amu2018_biomass_p)
amu2018_biomass_p = amu2018_biomass_p.reset_index()           # Pivoting will change columns to indexes. Change them back.

amu2018_biomass_p = amu2018_biomass_p.rename(
    columns={
        "biomass_total_kg_countries_reporting_amu_data":"biomass_total_kg_reporting"
        ,"biomass_total_kg_total_region":"biomass_total_kg_region"
        ,"biomass_total_terr_kg_countries_reporting_amu_data":"biomass_terr_kg_reporting"
        ,"biomass_total_terr_kg_total_region":"biomass_terr_kg_region"
        }
)
datainfo(amu2018_biomass_p)

# Merge usage and biomass
# Keep total usage, drop antimicrobial-specific usage
amu_combined_regional = pd.merge(
    left=amu2018.query("scope == 'All'").query("region != 'Global'")[['region' ,'number_of_countries' ,'total_antimicrobials_tonnes']]
    ,right=amu2018_biomass_p
    ,on='region'
    ,how='left'
)

# -----------------------------------------------------------------------------
# Find proportion of AM usage going to terrestrial food producing animals
# -----------------------------------------------------------------------------
# Calculate proportion of biomass
amu_combined_regional['biomass_terr_prpn_reporting'] = amu_combined_regional['biomass_terr_kg_reporting'] / amu_combined_regional['biomass_total_kg_reporting']
amu_combined_regional['terr_amu_tonnes_reporting'] = amu_combined_regional['total_antimicrobials_tonnes'] * amu_combined_regional['biomass_terr_prpn_reporting']

# -----------------------------------------------------------------------------
# Adjust for 2020
# -----------------------------------------------------------------------------
# Based on 2016-2018 trends
# Source: https://www.woah.org/app/uploads/2022/06/a-sixth-annual-report-amu-final-1.pdf
# "All OIE Regions presented a decrease as follows:
#    13% in Africa; 28% in the Americas; 30% in Asia, Far East and Oceania; and 18% in Europe."
# No regional trend available for Middle East. Using global average of 27% decrease.
amu_2020_adjustment = pd.DataFrame(
    {"region":['Africa' ,'Americas' ,'Asia, Far East and Oceania' ,'Europe' ,'Middle East']
     ,"prpn_change_2018to2020":[-0.13 ,-0.28 ,-0.30 ,-0.18 ,-0.27]
     }
)
amu_combined_regional = pd.merge(
    left=amu_combined_regional
    ,right=amu_2020_adjustment
    ,on='region'
    ,how='left'
)
amu_combined_regional['terr_amu_tonnes_reporting_2020'] = \
    amu_combined_regional['terr_amu_tonnes_reporting'] * (1 + amu_combined_regional['prpn_change_2018to2020'])

# -----------------------------------------------------------------------------
# Add estimate of region-total AMU by extrapolating from the countries reporting
# -----------------------------------------------------------------------------
# Terrestrial biomass among countries reporting as proportion of whole region
amu_combined_regional['biomass_terr_reporting_prpnofregion'] =\
    amu_combined_regional['biomass_terr_kg_reporting'] / amu_combined_regional['biomass_terr_kg_region']

amu_combined_regional['terr_amu_tonnes_region_2020'] =\
    amu_combined_regional['terr_amu_tonnes_reporting_2020'] / amu_combined_regional['biomass_terr_reporting_prpnofregion']

datainfo(amu_combined_regional)

# =============================================================================
#### Add Mulchandani data
# =============================================================================
# Sum Mulchandani to region level
amu_mulch_regional = amu_mulch_withrgn.pivot_table(
    index='woah_region'
# 	,values=['tonnes2020' ,'tonnes2030' ,'pcu__kg__2020' ,'pcu__kg__2030']
	,values='tonnes2020'
	,aggfunc='sum'
)

# Recalculate usage per PCU
# amu_mulch_regional['mgpcu_2020'] = amu_mulch_regional['tonnes2020'] * 1e9 / amu_mulch_regional['pcu__kg__2020']
# amu_mulch_regional['mgpcu_2030'] = amu_mulch_regional['tonnes2030'] * 1e9 / amu_mulch_regional['pcu__kg__2030']

amu_mulch_regional = amu_mulch_regional.rename(
    columns={
        "tonnes2020":"terr_amu_tonnes_mulch_2020"
        }
)
datainfo(amu_mulch_regional)

# Merge
amu_combined_regional = pd.merge(
    left=amu_combined_regional
    ,right=amu_mulch_regional
    ,left_on='region'
    ,right_on='woah_region'
    ,how='left'
)

# =============================================================================
#### Add prices
# =============================================================================
amu_combined_regional = pd.merge(
    left=amu_combined_regional
    ,right=amu_prices
    ,on='region'
    ,how='left'
)

# =============================================================================
#### Export
# =============================================================================
datainfo(amu_combined_regional)

amu_combined_regional.to_csv(os.path.join(PRODATA_FOLDER ,'amu_combined_regional.csv') ,index=False)
amu_combined_regional.to_csv(os.path.join(DASH_DATA_FOLDER ,'amu_combined_regional.csv') ,index=False)

#%% DEV: Resistance data

#%% DEV: AM Usage and Price with uncertainty

# =============================================================================
#### Create data based on spreadsheet from Sara
# =============================================================================
amu_uncertainty_data = pd.DataFrame(
    {"region":['Africa' ,'Americas' ,'Asia, Far East and Oceania' ,'Europe' ,'Middle East']
     ,"n_countries":[24 ,19 ,22 ,41 ,3]

     ,"amu_terrestrial_tonnes_min":[1403 ,18753 ,33387 ,7314 ,34]
     ,"amu_terrestrial_tonnes_mostlikely":[2806 ,29000 ,50080 ,7679.5 ,198]
     ,"amu_terrestrial_tonnes_max":[3086 ,31900 ,55088 ,8045 ,218]
     ,"amu_terrestrial_tonnes_distr":['Pert' ,'Pert' ,'Pert' ,'Uniform' ,'Pert']
     ,"amu_terrestrial_tonnes_distr_lambda":[np.nan ,np.nan ,np.nan ,np.nan ,np.nan]

     ,"amu_eurospertonne_min":[20476 ,20476 ,20476 ,np.nan ,20476]
     ,"amu_eurospertonne_mostlikely":[176992 ,82775.5 ,108806 ,145075 ,108806]
     ,"amu_eurospertonne_max":[206007 ,145075 ,123314 ,np.nan ,123314]
     ,"amu_eurospertonne_distr":['Modified pert; Ƴ=2.5' ,'Uniform' ,'Modified pert; Ƴ=2.5' ,'' ,'Modified pert; Ƴ=2.5']
     ,"amu_eurospertonne_distr_lambda":[2.5 ,np.nan ,2.5 ,np.nan ,2.5]
     }
)

# Merge in biomass data
amu_uncertainty_data = pd.merge(
    left=amu_uncertainty_data
    ,right=amu2018_biomass.query("segment == 'Countries reporting AMU data'")[['region' ,'biomass_total_kg' ,'biomass_total_terr_kg']]
    ,on='region'
    ,how='left'
)

datainfo(amu_uncertainty_data)

usage_cols = ['amu_terrestrial_tonnes_min' ,'amu_terrestrial_tonnes_mostlikely' ,'amu_terrestrial_tonnes_max']
price_cols = ['amu_eurospertonne_min' ,'amu_eurospertonne_mostlikely' ,'amu_eurospertonne_max']

amu_uncertainty_data_toplot_usage = amu_uncertainty_data.copy()
amu_uncertainty_data_toplot_usage[price_cols] = np.nan

amu_uncertainty_data_toplot_price = amu_uncertainty_data.copy()
amu_uncertainty_data_toplot_price[usage_cols] = np.nan
amu_uncertainty_data_toplot_price['region'] = amu_uncertainty_data_toplot_price['region'] + '_price'

amu_uncertainty_data_toplot = pd.concat([amu_uncertainty_data_toplot_usage ,amu_uncertainty_data_toplot_price] ,axis=0 ,ignore_index=True)
amu_uncertainty_data_toplot = amu_uncertainty_data_toplot.sort_values(by='region')

# =============================================================================
#### Add confidence intervals for usage
# =============================================================================
def add_ci(INPUT_ROW):
    # Usage
    if 'PERT' in INPUT_ROW['amu_terrestrial_tonnes_distr'].upper():
        # Get Beta distribution and calculate CI
        if pd.notnull(INPUT_ROW['amu_terrestrial_tonnes_distr_lambda']):
            beta_distr_tonnes = pert_to_beta(
                INPUT_ROW['amu_terrestrial_tonnes_min']
                ,INPUT_ROW['amu_terrestrial_tonnes_mostlikely']
                ,INPUT_ROW['amu_terrestrial_tonnes_max']
                ,INPUT_ROW['amu_terrestrial_tonnes_distr_lambda']
            )
        else:
            beta_distr_tonnes = pert_to_beta(
                INPUT_ROW['amu_terrestrial_tonnes_min']
                ,INPUT_ROW['amu_terrestrial_tonnes_mostlikely']
                ,INPUT_ROW['amu_terrestrial_tonnes_max']
            )

        beta_distr_tonnes_ci95 = beta_distr_tonnes.interval(0.95)

        # Rescale CI to match original Pert
        tonnes_ci95_low = (beta_distr_tonnes_ci95[0] * (INPUT_ROW['amu_terrestrial_tonnes_max'] - INPUT_ROW['amu_terrestrial_tonnes_min'])) + INPUT_ROW['amu_terrestrial_tonnes_min']   # Translate from (0,1) to scale of PERT
        tonnes_ci95_high = (beta_distr_tonnes_ci95[1] * (INPUT_ROW['amu_terrestrial_tonnes_max'] - INPUT_ROW['amu_terrestrial_tonnes_min'])) + INPUT_ROW['amu_terrestrial_tonnes_min']   # Translate from (0,1) to scale of PERT
    elif INPUT_ROW['amu_terrestrial_tonnes_distr'].upper() == 'UNIFORM':
        tonnes_ci95_low = 0.025*(INPUT_ROW['amu_terrestrial_tonnes_max'] - INPUT_ROW['amu_terrestrial_tonnes_min']) + INPUT_ROW['amu_terrestrial_tonnes_min']
        tonnes_ci95_high = 0.975*(INPUT_ROW['amu_terrestrial_tonnes_max'] - INPUT_ROW['amu_terrestrial_tonnes_min']) + INPUT_ROW['amu_terrestrial_tonnes_min']
    else:
        tonnes_ci95_low = None
        tonnes_ci95_high = None

    # Price
    if 'PERT' in INPUT_ROW['amu_eurospertonne_distr'].upper():
        # Get Beta distribution and calculate CI
        if pd.notnull(INPUT_ROW['amu_eurospertonne_distr_lambda']):
            beta_distr_price = pert_to_beta(
                INPUT_ROW['amu_eurospertonne_min']
                ,INPUT_ROW['amu_eurospertonne_mostlikely']
                ,INPUT_ROW['amu_eurospertonne_max']
                ,INPUT_ROW['amu_eurospertonne_distr_lambda']
            )
        else:
            beta_distr_price = pert_to_beta(
                INPUT_ROW['amu_eurospertonne_min']
                ,INPUT_ROW['amu_eurospertonne_mostlikely']
                ,INPUT_ROW['amu_eurospertonne_max']
            )

        beta_distr_price_ci95 = beta_distr_price.interval(0.95)

        # Rescale CI to match original Pert
        price_ci95_low = (beta_distr_price_ci95[0] * (INPUT_ROW['amu_eurospertonne_max'] - INPUT_ROW['amu_eurospertonne_min'])) + INPUT_ROW['amu_eurospertonne_min']   # Translate from (0,1) to scale of PERT
        price_ci95_high = (beta_distr_price_ci95[1] * (INPUT_ROW['amu_eurospertonne_max'] - INPUT_ROW['amu_eurospertonne_min'])) + INPUT_ROW['amu_eurospertonne_min']   # Translate from (0,1) to scale of PERT
    elif INPUT_ROW['amu_eurospertonne_distr'].upper() == 'UNIFORM':
        price_ci95_low = 0.025*(INPUT_ROW['amu_eurospertonne_max'] - INPUT_ROW['amu_eurospertonne_min']) + INPUT_ROW['amu_eurospertonne_min']
        price_ci95_high = 0.975*(INPUT_ROW['amu_eurospertonne_max'] - INPUT_ROW['amu_eurospertonne_min']) + INPUT_ROW['amu_eurospertonne_min']
    else:
        price_ci95_low = None
        price_ci95_high = None

    return pd.Series([tonnes_ci95_low ,tonnes_ci95_high ,price_ci95_low ,price_ci95_high])

amu_uncertainty_data[['tonnes_ci95_low' ,'tonnes_ci95_high' ,'price_ci95_low' ,'price_ci95_high']] = amu_uncertainty_data.apply(add_ci ,axis=1)

#??? Should intervals be centered on the MOST LIKELY value or the MEAN?
amu_uncertainty_data = amu_uncertainty_data.eval(
    '''
    amu_terrestrial_tonnes_errorlow = amu_terrestrial_tonnes_mostlikely - tonnes_ci95_low
    amu_terrestrial_tonnes_errorhigh = tonnes_ci95_high - amu_terrestrial_tonnes_mostlikely

    amu_eurospertonne_errorlow = amu_eurospertonne_mostlikely - price_ci95_low
    amu_eurospertonne_errorhigh = price_ci95_high - amu_eurospertonne_mostlikely
    '''
)

# =============================================================================
#### Generate distribution of total expenditure
# =============================================================================
# For each region, resample from Usage and Price distributions and multiply to get expenditure
resample_n = 10000

expenditure_africa = pd.DataFrame(index=range(resample_n))
expenditure_africa['resampled_usage'] = generate_pert(resample_n, 1403, 2806, 3086)['rand_pert']
expenditure_africa['resampled_price'] = generate_pert(resample_n, 20476, 176992, 206007 ,2.5)['rand_pert']
expenditure_africa['resampled_expenditure'] = expenditure_africa['resampled_usage'] * expenditure_africa['resampled_price']
expenditure_africa['expenditure_pctile'] = expenditure_africa['resampled_expenditure'].rank(pct=True)

expenditure_americas = pd.DataFrame(index=range(resample_n))
expenditure_americas['resampled_usage'] = generate_pert(resample_n, 18753, 29000, 31900)['rand_pert']
expenditure_americas['resampled_price'] = sps.uniform.rvs(loc=20476 ,scale=145075 ,size=resample_n)
expenditure_americas['resampled_expenditure'] = expenditure_americas['resampled_usage'] * expenditure_americas['resampled_price']
expenditure_americas['expenditure_pctile'] = expenditure_americas['resampled_expenditure'].rank(pct=True)

expenditure_asia = pd.DataFrame(index=range(resample_n))
expenditure_asia['resampled_usage'] = generate_pert(resample_n, 33387, 50080, 55088)['rand_pert']
expenditure_asia['resampled_price'] = generate_pert(resample_n, 20476, 108806, 123314 ,2.5)['rand_pert']
expenditure_asia['resampled_expenditure'] = expenditure_asia['resampled_usage'] * expenditure_asia['resampled_price']
expenditure_asia['expenditure_pctile'] = expenditure_asia['resampled_expenditure'].rank(pct=True)

expenditure_europe = pd.DataFrame(index=range(resample_n))
expenditure_europe['resampled_usage'] = sps.uniform.rvs(loc=7314 ,scale=8045 ,size=resample_n)
expenditure_europe['resampled_price'] = 145075
expenditure_europe['resampled_expenditure'] = expenditure_europe['resampled_usage'] * expenditure_europe['resampled_price']
expenditure_europe['expenditure_pctile'] = expenditure_europe['resampled_expenditure'].rank(pct=True)

expenditure_mideast = pd.DataFrame(index=range(resample_n))
expenditure_mideast['resampled_usage'] = generate_pert(resample_n, 34, 198, 218)['rand_pert']
expenditure_mideast['resampled_price'] = generate_pert(resample_n, 20476, 108806, 123314 ,2.5)['rand_pert']
expenditure_mideast['resampled_expenditure'] = expenditure_mideast['resampled_usage'] * expenditure_mideast['resampled_price']
expenditure_mideast['expenditure_pctile'] = expenditure_mideast['resampled_expenditure'].rank(pct=True)

# Plot
snplt = sns.displot(
	data=expenditure_mideast
	,x='resampled_expenditure'
	,kind='hist'
    ,stat='probability'
    ,bins=20
)

# Get CI for expenditure from percentiles of the resampled distribution
def add_expenditure_ci(REGION):
    if REGION.upper() == 'AFRICA':
        ci_low = expenditure_africa.query("expenditure_pctile == 0.025")['resampled_expenditure'].values[0]
        ci_mid = expenditure_africa.query("expenditure_pctile == 0.5")['resampled_expenditure'].values[0]
        ci_high = expenditure_africa.query("expenditure_pctile == 0.975")['resampled_expenditure'].values[0]
    elif REGION.upper() == 'AMERICAS':
        ci_low = expenditure_americas.query("expenditure_pctile == 0.025")['resampled_expenditure'].values[0]
        ci_mid = expenditure_americas.query("expenditure_pctile == 0.5")['resampled_expenditure'].values[0]
        ci_high = expenditure_americas.query("expenditure_pctile == 0.975")['resampled_expenditure'].values[0]
    elif 'ASIA' in REGION.upper():
        ci_low = expenditure_asia.query("expenditure_pctile == 0.025")['resampled_expenditure'].values[0]
        ci_mid = expenditure_asia.query("expenditure_pctile == 0.5")['resampled_expenditure'].values[0]
        ci_high = expenditure_asia.query("expenditure_pctile == 0.975")['resampled_expenditure'].values[0]
    elif REGION.upper() == 'EUROPE':
        ci_low = expenditure_europe.query("expenditure_pctile == 0.025")['resampled_expenditure'].values[0]
        ci_mid = expenditure_europe.query("expenditure_pctile == 0.5")['resampled_expenditure'].values[0]
        ci_high = expenditure_europe.query("expenditure_pctile == 0.975")['resampled_expenditure'].values[0]
    elif REGION.upper() == 'MIDDLE EAST':
        ci_low = expenditure_mideast.query("expenditure_pctile == 0.025")['resampled_expenditure'].values[0]
        ci_mid = expenditure_mideast.query("expenditure_pctile == 0.5")['resampled_expenditure'].values[0]
        ci_high = expenditure_mideast.query("expenditure_pctile == 0.975")['resampled_expenditure'].values[0]
    else:
        ci_low = np.nan
        ci_mid = np.nan
        ci_high = np.nan
    return pd.Series([ci_low ,ci_mid ,ci_high])
amu_uncertainty_data[['expenditure_ci95_low' ,'expenditure_ci95_mid' ,'expenditure_ci95_high']] = amu_uncertainty_data['region'].apply(add_expenditure_ci)

amu_uncertainty_data = amu_uncertainty_data.eval(
    '''
    amu_terrestrial_expenditure_midpoint = expenditure_ci95_mid
    amu_terrestrial_expenditure_errorlow = amu_terrestrial_expenditure_midpoint - expenditure_ci95_low
    amu_terrestrial_expenditure_errorhigh = expenditure_ci95_high - amu_terrestrial_expenditure_midpoint
    '''
)

# =============================================================================
#### Export
# =============================================================================
datainfo(amu_uncertainty_data)

amu_uncertainty_data.to_csv(os.path.join(DASH_DATA_FOLDER, "amu_uncertainty_data.csv"))
