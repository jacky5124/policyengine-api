from policyengine_api.country import COUNTRIES, create_policy_reform
from policyengine_core.simulations import Microsimulation
from policyengine_core.experimental import MemoryConfig
import json


def compute_general_economy(
    simulation: Microsimulation, country_id: str = None
) -> dict:
    total_tax = simulation.calculate("household_tax").sum()
    personal_hh_equiv_income = simulation.calculate(
        "equiv_household_net_income"
    )
    household_count_people = simulation.calculate("household_count_people")
    personal_hh_equiv_income.weights *= household_count_people
    try:
        gini = personal_hh_equiv_income.gini()
    except:
        print(
            "WARNING: Gini index calculations resulted in an error: returning no change, but this is inaccurate."
        )
        gini = 0.4
    in_top_10_pct = personal_hh_equiv_income.decile_rank() == 10
    in_top_1_pct = personal_hh_equiv_income.percentile_rank() == 100
    personal_hh_equiv_income.weights /= household_count_people
    top_10_percent_share = (
        personal_hh_equiv_income[in_top_10_pct].sum()
        / personal_hh_equiv_income.sum()
    )
    top_1_percent_share = (
        personal_hh_equiv_income[in_top_1_pct].sum()
        / personal_hh_equiv_income.sum()
    )
    try:
        wealth = simulation.calculate("total_wealth")
        wealth.weights *= household_count_people
        wealth_decile = wealth.decile_rank().astype(int).tolist()
        wealth = wealth.astype(float).tolist()
    except:
        wealth = None
        wealth_decile = None
    try:
        is_male = simulation.calculate("is_male").astype(bool).tolist()
    except:
        is_male = None
    try:
        race = simulation.calculate("race").astype(str).tolist()
    except:
        race = None
    try:
        total_state_tax = simulation.calculate("state_income_tax").sum()
    except Exception as e:
        total_state_tax = 0

    result = {
        "total_net_income": simulation.calculate("household_net_income").sum(),
        "total_tax": total_tax,
        "total_state_tax": total_state_tax,
        "total_benefits": simulation.calculate("household_benefits").sum(),
        "household_net_income": simulation.calculate("household_net_income")
        .astype(float)
        .tolist(),
        "equiv_household_net_income": simulation.calculate(
            "equiv_household_net_income",
        )
        .astype(float)
        .tolist(),
        "household_income_decile": simulation.calculate(
            "household_income_decile"
        )
        .astype(int)
        .tolist(),
        "household_wealth_decile": wealth_decile,
        "household_wealth": wealth,
        "in_poverty": simulation.calculate("in_poverty").astype(bool).tolist(),
        "person_in_poverty": simulation.calculate(
            "in_poverty", map_to="person"
        )
        .astype(bool)
        .tolist(),
        "person_in_deep_poverty": simulation.calculate(
            "in_deep_poverty", map_to="person"
        )
        .astype(bool)
        .tolist(),
        "poverty_gap": simulation.calculate("poverty_gap").sum(),
        "deep_poverty_gap": simulation.calculate("deep_poverty_gap").sum(),
        "person_weight": simulation.calculate("person_weight")
        .astype(float)
        .tolist(),
        "age": simulation.calculate("age").astype(int).tolist(),
        "household_weight": simulation.calculate("household_weight")
        .astype(float)
        .tolist(),
        "household_count_people": simulation.calculate(
            "household_count_people"
        )
        .astype(int)
        .tolist(),
        "gini": float(gini),
        "top_10_percent_share": float(top_10_percent_share),
        "top_1_percent_share": float(top_1_percent_share),
        "is_male": is_male,
        "race": race,
        "type": "general",
        "programs": {},
    }
    if country_id == "uk":
        PROGRAMS = [
            "income_tax",
            "national_insurance",
            "vat",
            "council_tax",
            "fuel_duty",
            "tax_credits",
            "universal_credit",
            "child_benefit",
            "state_pension",
            "pension_credit",
        ]
        IS_POSITIVE = [True] * 5 + [False] * 5
        for program in PROGRAMS:
            result["programs"][program] = simulation.calculate(
                program, map_to="household"
            ).sum() * (1 if IS_POSITIVE[PROGRAMS.index(program)] else -1)
    return result


def compute_cliff_impact(
    simulation: Microsimulation,
):
    cliff_gap = simulation.calculate("cliff_gap")
    is_on_cliff = simulation.calculate("is_on_cliff")
    total_cliff_gap = cliff_gap.sum()
    total_adults = simulation.calculate("is_adult").sum()
    cliff_share = is_on_cliff.sum() / total_adults
    return {
        "cliff_gap": float(total_cliff_gap),
        "cliff_share": float(cliff_share),
        "type": "cliff",
    }


def compute_economy(
    country_id: str,
    policy_id: str,
    region: str,
    time_period: str,
    options: dict,
    policy_json: dict,
):
    country = COUNTRIES.get(country_id)
    policy_data = json.loads(policy_json)
    if country_id == "us":
        us_modelled_states = country.tax_benefit_system.modelled_policies[
            "filtered"
        ]["state_name"].keys()
        us_modelled_states = [state.lower() for state in us_modelled_states]
        if (region == "us") or (
            region.lower() not in us_modelled_states + ["nyc"]
        ):
            print(f"Setting state taxes to reported")
            policy_data["simulation.reported_state_income_tax"] = {
                "2010-01-01.2030-01-01": True
            }
    reform = create_policy_reform(policy_data)

    print("Initialising microsimulation")

    simulation: Microsimulation = country.country_package.Microsimulation(
        reform=reform,
    )
    simulation.default_calculation_period = time_period

    original_household_weight = simulation.calculate("household_weight").values

    if country_id == "uk":
        if region != "uk":
            region_values = simulation.calculate("country").values
            region_decoded = dict(
                eng="ENGLAND",
                wales="WALES",
                scot="SCOTLAND",
                ni="NORTHERN_IRELAND",
            )[region]
            simulation.set_input(
                "household_weight",
                time_period,
                original_household_weight * (region_values == region_decoded),
            )
    elif country_id == "us":
        if region != "us":
            if region == "nyc":
                in_nyc = simulation.calculate("in_nyc").values
                simulation.set_input(
                    "household_weight",
                    time_period,
                    original_household_weight * in_nyc,
                )
            else:
                region_values = simulation.calculate("state_code_str").values
                simulation.set_input(
                    "household_weight",
                    time_period,
                    original_household_weight
                    * (region_values == region.upper()),
                )
    for time_period in simulation.get_holder(
        "person_weight"
    ).get_known_periods():
        simulation.delete_arrays("person_weight", time_period)

    if options.get("target") == "cliff":
        return compute_cliff_impact(simulation)

    print("Calculating tax and benefits")

    return compute_general_economy(simulation, country_id=country_id)
