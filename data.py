from datetime import date, timedelta
import random
from decimal import Decimal

from crop.core.models import (
    Mukkadam, ContactInfo, TeamMember, SubTeam, TeamDeployment,
    CrewCapacityHistory, RateCard, PaymentMethod, WorkAreaPreference,
    TransportConfig, MemberAvailability,
    SubTeamAvailabilitySnapshot, MukkadamAvailabilityRollup,
    WorkAssignment
)
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crop.settings")
django.setup()

random.seed(42)


def clear_all():
    WorkAssignment.objects.all().delete()
    SubTeamAvailabilitySnapshot.objects.all().delete()
    MukkadamAvailabilityRollup.objects.all().delete()
    MemberAvailability.objects.all().delete()
    TransportConfig.objects.all().delete()
    WorkAreaPreference.objects.all().delete()
    PaymentMethod.objects.all().delete()
    RateCard.objects.all().delete()
    CrewCapacityHistory.objects.all().delete()
    TeamDeployment.objects.all().delete()
    SubTeam.objects.all().delete()
    TeamMember.objects.all().delete()
    ContactInfo.objects.all().delete()
    Mukkadam.objects.all().delete()


def create_mukkadam(index, name, home_village, home_taluka, total_capacity):
    muk_id = f"MUK{index:04}"
    m = Mukkadam.objects.create(
        mukkadam_id=muk_id,
        full_name=name,
        primary_mobile=f"98{random.randint(10000000, 99999999)}",
        home_village=home_village,
        home_taluka=home_taluka,
        total_team_capacity=total_capacity,
        team_structure_type='split' if total_capacity > 12 else 'single',
        is_active=True,
        has_smartphone=True,
        referral_source=random.choice(["Farmer referral", "Field officer", "WhatsApp ad"])
    )
    return m


def create_contacts(m):
    nums = [m.primary_mobile,
            f"99{random.randint(10000000, 99999999)}"]
    for i, num in enumerate(nums):
        ContactInfo.objects.create(
            mukkadam=m,
            mobile_number=num,
            contact_type='primary' if i == 0 else 'secondary',
            is_active=True,
            priority=i + 1
        )


def create_team_members(m):
    members = []
    for i in range(m.total_team_capacity):
        member = TeamMember.objects.create(
            mukkadam=m,
            member_id=f"{m.mukkadam_id}-M{i+1:03}",
            member_name=f"{m.full_name.split()[0]} Worker {i+1}",
            mobile_number='' if random.random() < 0.5 else f"97{random.randint(10000000, 99999999)}",
            skill_pruning=bool(random.getrandbits(1)),
            skill_harvesting=bool(random.getrandbits(1)),
            skill_dipping=bool(random.getrandbits(1)),
            skill_thinning=bool(random.getrandbits(1)),
            skill_shoot_tying=bool(random.getrandbits(1)),
            skill_cane_tying=bool(random.getrandbits(1)),
            experience_level=random.choice(['novice', 'intermediate', 'experienced', 'expert']),
            can_be_deputy=random.random() < 0.3,
            is_active=True
        )
        members.append(member)
    return members


def create_subteams_and_deploy(m, members):
    subteams = []
    remaining = len(members)
    cursor = 0

    # choose random chunk sizes between 8 and 15, but not exceeding remaining
    t = 1
    while remaining > 0:
        size = min(random.randint(8, 15), remaining)
        st = SubTeam.objects.create(
            mukkadam=m,
            sub_team_id=f"{m.mukkadam_id}-T{t}",
            sub_team_name=f"Team {t}",
            deputy_mukkadam_name=f"Deputy {t} {m.full_name.split()[0]}",
            deputy_mobile=f"96{random.randint(10000000, 99999999)}",
            max_capacity=size,
            current_size=size,
            default_work_area=m.home_village,
            is_active=True,
            deployment_status='deployed' if random.random() < 0.7 else 'available',
            autonomy_level=random.choice(['full', 'partial', 'supervised'])
        )
        subteams.append(st)

        for mem in members[cursor:cursor+size]:
            role = 'deputy' if mem.can_be_deputy and random.random() < 0.1 else 'member'
            TeamDeployment.objects.create(
                member=mem,
                sub_team=st,
                start_date=date(2025, 11, 1),
                role=role,
                is_active=True
            )
        cursor += size
        remaining -= size
        t += 1

    # capacity history
    CrewCapacityHistory.objects.create(
        mukkadam=m,
        crew_size=len(members),
        max_capacity=m.total_team_capacity,
        deputy_mukkadam_name=subteams[0].deputy_mukkadam_name if subteams else "",
        splitting_logic="Auto-created demo split into variable-size teams",
        valid_from=date(2025, 10, 1),
        valid_until=None,
        is_active=True,
        reason="Initial registration"
    )

    return subteams


def create_rate_cards(m):
    # default all-area card
    RateCard.objects.create(
        mukkadam=m,
        rate_card_name=f"Default {m.home_village} Card",
        applicable_villages=m.home_village,
        applicable_taluka=m.home_taluka,
        valid_from=date(2025, 10, 1),
        valid_until=None,
        is_active=True,
        is_default=True,
        fail_foot=Decimal("450.00"),
        second_fail=Decimal("550.00"),
        dipping=Decimal("500.00"),
        thinning=Decimal("400.00"),
        shoot_tying=Decimal("350.00"),
        cane_tying=Decimal("380.00"),
        shenda_stop=Decimal("300.00"),
        general_expected_charges=450
    )

    # premium card for one extra village
    extra_village = random.choice(["Harsul", "Trimbakeshwar", "Ladse"])
    RateCard.objects.create(
        mukkadam=m,
        rate_card_name=f"{extra_village} Premium Card",
        applicable_villages=extra_village.lower(),
        applicable_taluka=m.home_taluka,
        valid_from=date(2025, 11, 1),
        valid_until=None,
        is_active=True,
        is_default=False,
        fail_foot=Decimal("550.00"),
        second_fail=Decimal("650.00"),
        dipping=Decimal("600.00"),
        thinning=Decimal("480.00"),
        shoot_tying=Decimal("420.00"),
        cane_tying=Decimal("450.00"),
        shenda_stop=Decimal("380.00"),
        general_expected_charges=550
    )


def create_payment_methods(m):
    PaymentMethod.objects.create(
        mukkadam=m,
        payment_type='upi',
        priority=1,
        is_active=True,
        is_verified=True,
        payment_details={"upi_id": f"{m.full_name.split()[0].lower()}@paytm"}
    )
    PaymentMethod.objects.create(
        mukkadam=m,
        payment_type='bank_transfer',
        priority=2,
        is_active=True,
        is_verified=True,
        payment_details={
            "account_number": f"{random.randint(10000000,99999999)}",
            "ifsc": "SBIN0001234",
            "bank_name": "SBI Nashik"
        }
    )
    PaymentMethod.objects.create(
        mukkadam=m,
        payment_type='cash',
        priority=3,
        is_active=True,
        is_verified=True,
        payment_details={"preferred_denomination": "500,100"}
    )


def create_work_areas(m):
    base_area = WorkAreaPreference.objects.create(
        mukkadam=m,
        village=m.home_village,
        taluka=m.home_taluka,
        district="Nashik",
        distance_from_home_km=5,
        max_travel_distance_km=40,
        preferred_work_mode='daily',
        is_active=True,
        available_from=date(2025, 10, 1),
        priority=1
    )
    extra_villages = ["Harsul", "Trimbakeshwar", "Ladse"]
    for i, v in enumerate(extra_villages, start=2):
        WorkAreaPreference.objects.create(
            mukkadam=m,
            village=v,
            taluka=m.home_taluka,
            district="Nashik",
            distance_from_home_km=random.randint(15, 60),
            max_travel_distance_km=60,
            preferred_work_mode=random.choice(['move_in', 'both']),
            is_active=True,
            available_from=date(2025, 11, 1),
            priority=i,
            associated_rate_card=m.rate_cards.filter(rate_card_name__icontains=v).first()
        )


def create_transport_configs(m):
    TransportConfig.objects.create(
        mukkadam=m,
        transport_mode='own_bike',
        charge_per_km=Decimal("8.0"),
        charge_per_trip=Decimal("0.0"),
        charge_per_bike=Decimal("100.0"),
        beyond_km=20,
        arranged_by='mukkadam',
        is_active=True,
        valid_from=date(2025, 10, 1),
        valid_until=date(2025, 11, 15),
        currently_stationed_at=m.home_village
    )
    TransportConfig.objects.create(
        mukkadam=m,
        transport_mode='no_vehicle',
        charge_per_km=Decimal("0.0"),
        charge_per_trip=Decimal("0.0"),
        charge_per_bike=Decimal("0.0"),
        beyond_km=0,
        arranged_by='bi',
        is_active=True,
        valid_from=date(2025, 11, 16),
        valid_until=None,
        currently_stationed_at=m.home_village,
        notes="Bike broken, company arranging pickup."
    )


def create_member_availability(members):
    today = date(2025, 11, 20)
    for mem in random.sample(members, k=min(5, len(members))):
        MemberAvailability.objects.create(
            member=mem,
            start_date=today,
            end_date=today + timedelta(days=random.randint(2, 5)),
            status=random.choice(['sick', 'vacation', 'committed']),
            reason=random.choice(['Fever', 'Family function', 'Working for other farm']),
            committed_to="Other contractor" if random.random() < 0.3 else None,
            priority=10,
            is_active=True
        )


def create_work_assignments(m, subteams):
    today = date(2025, 11, 20)
    for i, st in enumerate(subteams, start=1):
        village = random.choice(
            [wa.village for wa in m.work_areas.filter(is_active=True)]
        )
        rc = (m.rate_cards
              .filter(applicable_villages__iexact=village)

              .order_by('-is_default')
              .first())
        if rc is None:
            rc = m.rate_cards.filter(is_default=True).first()

        # Still if None → raise helpful errorexit()
        if rc is None:
            raise Exception(f"No rate card found for village: {village} for mukkadam {m.mukkadam_id}")
        activity = random.choice(
            ['fail_foot', 'dipping', 'thinning', 'shoot_tying']
        )
        team_size = st.current_size
        rate = getattr(rc, activity)
        total = rate * team_size

        WorkAssignment.objects.create(
            assignment_id=f"WA-{m.mukkadam_id}-{i:03}",
            sub_team=st,
            work_village=village,
            work_taluka=m.home_taluka,
            farm_name=f"{village} Farm {i}",
            farm_owner=f"Farmer {i} {village}",
            activity_type=activity,
            rate_card=rc,
            agreed_rate=rate,
            start_date=today,
            estimated_end_date=today + timedelta(days=random.randint(5, 15)),
            actual_end_date=None,
            team_size=team_size,
            status='active',
            total_amount_due=total,
            amount_paid=Decimal("0.0"),
            is_active=True
        )


def recalc_availability(m):
    today = date(2025, 11, 20)
    for st in m.sub_teams.all():
        SubTeamAvailabilitySnapshot.calculate_for_date(st, today)
    MukkadamAvailabilityRollup.calculate_for_date(m, today)


def populate_dummy_data():
    clear_all()

    mukkadam_specs = [
        (11, "Sham Bhaurao Bendph", "Girnar", "Nashik", 55),
        (21, "Sharad Rujaji Bhor", "Harsu", "Nashik", 18),
        (31, "Vilas Sharma Div", "Lads", "Peth", 10),
    ]

    for idx, name, village, taluka, cap in mukkadam_specs:
        m = create_mukkadam(idx, name, village, taluka, cap)
        create_contacts(m)
        members = create_team_members(m)
        subteams = create_subteams_and_deploy(m, members)
        create_rate_cards(m)
        create_payment_methods(m)
        create_work_areas(m)
        create_transport_configs(m)
        create_member_availability(members)
        create_work_assignments(m, subteams)
        recalc_availability(m)

    print("✅ Dummy data populated for all models.")


# Run this:
populate_dummy_data()
