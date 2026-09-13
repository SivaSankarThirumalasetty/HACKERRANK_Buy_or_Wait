import re
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from src.models.domain import Decision, Request, FinancialProfile, PaymentOption, FinancialEvent
from src.models.spending_change import SpendingChange
from src.validation.installment_validator import validate_installment_schedule
from src.normalization.events import build_recurring_streams

def validate_all_decisions(
    decisions: List[Decision],
    requests: List[Request],
    profiles: Dict[str, FinancialProfile],
    payment_options: Dict[str, List[PaymentOption]],
    events: List[FinancialEvent]
) -> List[str]:
    """
    Strict validator implementing all 17 required checks.
    Returns a list of error strings. If empty, all checks passed.
    """
    errors: List[str] = []

    # Map lookups
    req_map = {r.request_id: r for r in requests}
    dec_map = {}
    
    # 1. Every request_id appears exactly once & 2. No extra request IDs
    for d in decisions:
        if d.request_id in dec_map:
            errors.append(f"Rule 1 Violation: Duplicate request_id {d.request_id} in decisions.")
        dec_map[d.request_id] = d
        if d.request_id not in req_map:
            errors.append(f"Rule 2 Violation: Extra request_id {d.request_id} not found in requests.csv.")

    for r_id in req_map:
        if r_id not in dec_map:
            errors.append(f"Rule 1 Violation: Missing request_id {r_id} from decisions.")

    # Validate each decision
    allowed_statuses = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
    allowed_methods = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}

    for d in decisions:
        r_id = d.request_id
        if r_id not in req_map:
            continue
        req = req_map[r_id]
        prof = profiles.get(req.user_id)
        opts = payment_options.get(r_id, [])

        # 3. amount_safe_to_pay is numeric
        if not isinstance(d.amount_safe_to_pay, (Decimal, int, float)):
            errors.append(f"Rule 3 Violation [{r_id}]: amount_safe_to_pay '{d.amount_safe_to_pay}' is not numeric.")
        else:
            amt_safe = Decimal(str(d.amount_safe_to_pay))
            # 4. 0 <= amount_safe_to_pay <= requested_amount
            if amt_safe < 0:
                errors.append(f"Rule 4 Violation [{r_id}]: amount_safe_to_pay {amt_safe} < 0.")
            if amt_safe > req.requested_amount:
                errors.append(f"Rule 4 Violation [{r_id}]: amount_safe_to_pay {amt_safe} > requested_amount {req.requested_amount}.")

        # 5. affordability_status is allowed
        if d.affordability_status not in allowed_statuses:
            errors.append(f"Rule 5 Violation [{r_id}]: affordability_status '{d.affordability_status}' not allowed.")

        # 6. recommended_payment_method is allowed
        if d.recommended_payment_method not in allowed_methods:
            errors.append(f"Rule 6 Violation [{r_id}]: recommended_payment_method '{d.recommended_payment_method}' not allowed.")

        # 16. not-recommended cases use payment_plan=none
        if d.recommended_payment_method == 'not_recommended':
            if d.payment_plan != 'none':
                errors.append(f"Rule 16 Violation [{r_id}]: not_recommended must have payment_plan='none', got '{d.payment_plan}'.")
            if d.affordability_status != 'not_affordable':
                errors.append(f"Rule 16 Violation [{r_id}]: not_recommended should have affordability_status='not_affordable', got '{d.affordability_status}'.")

        # Parse payment plan if not 'none'
        plan_payments: List[Tuple[date, Decimal]] = []
        if d.payment_plan != 'none':
            items = d.payment_plan.split('|')
            # 7. payment_plan syntax is valid
            for item in items:
                parts = item.split(':')
                if len(parts) != 2:
                    errors.append(f"Rule 7 Violation [{r_id}]: Invalid payment item format '{item}' in '{d.payment_plan}'.")
                    continue
                try:
                    dt = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
                    amt = Decimal(parts[1].strip())
                    plan_payments.append((dt, amt))
                except Exception as e:
                    errors.append(f"Rule 7 Violation [{r_id}]: Cannot parse payment item '{item}': {e}")

            # 8. payment dates are chronological
            for i in range(1, len(plan_payments)):
                if plan_payments[i][0] < plan_payments[i-1][0]:
                    errors.append(f"Rule 8 Violation [{r_id}]: Payment dates not chronological: {plan_payments[i-1][0]} followed by {plan_payments[i][0]}.")

        # 9. payment totals equal requested_amount whenever a full request is recommended (full_payment, partial_payment, wait)
        if d.recommended_payment_method in {'full_payment', 'wait'}:
            total_plan = sum(amt for _, amt in plan_payments)
            if total_plan != req.requested_amount:
                errors.append(f"Rule 9 Violation [{r_id}]: {d.recommended_payment_method} total {total_plan} != requested_amount {req.requested_amount}.")

        # 10. partial payment contains exactly two payments & 11. sum exactly to requested_amount
        if d.recommended_payment_method == 'partial_payment':
            if len(plan_payments) != 2:
                errors.append(f"Rule 10 Violation [{r_id}]: partial_payment has {len(plan_payments)} payments, expected exactly 2.")
            else:
                total_partial = plan_payments[0][1] + plan_payments[1][1]
                if total_partial != req.requested_amount:
                    errors.append(f"Rule 11 Violation [{r_id}]: partial_payment sum {total_partial} != requested_amount {req.requested_amount}.")
                # Also verify first payment is amount_safe_to_pay on request_date
                if plan_payments[0][0] != req.request_date:
                    errors.append(f"Rule 10 Violation [{r_id}]: partial_payment first payment date {plan_payments[0][0]} != request_date {req.request_date}.")
                if plan_payments[0][1] != amt_safe:
                    errors.append(f"Rule 10 Violation [{r_id}]: partial_payment first payment amount {plan_payments[0][1]} != amount_safe_to_pay {amt_safe}.")

        # 12. installment plan exactly matches supplied payment option across all 11 rules
        if d.recommended_payment_method == 'installments':
            available_opt_ids = {opt.payment_option_id for opt in opts}
            matched_option = None
            best_opt_errors = []

            for opt in opts:
                if opt.payment_method != 'installments':
                    continue
                errs = validate_installment_schedule(
                    option=opt,
                    payments=plan_payments,
                    profile=prof,
                    request=req,
                    expected_option_id=None,
                    completion_date=plan_payments[-1][0] if plan_payments else None,
                    available_option_ids=available_opt_ids
                )
                if not errs:
                    matched_option = opt
                    break
                else:
                    if not best_opt_errors or len(errs) < len(best_opt_errors):
                        best_opt_errors = errs

            if matched_option is None:
                err_detail = "; ".join(best_opt_errors) if best_opt_errors else "No installment options supplied"
                errors.append(f"Rule 12 Violation [{r_id}]: Installment plan '{d.payment_plan}' does not validly match any supplied payment option: {err_detail}")

        # 13. spending changes only reference flexible recurring expenses & respect user preferences
        if d.spending_changes_needed != 'none':
            sc_items = d.spending_changes_needed.split('|')
            if len(sc_items) > 3:
                errors.append(f"Rule 13 Violation [{r_id}]: More than 3 spending changes specified ({len(sc_items)} > 3).")

            user_events = [e for e in events if e.user_id == req.user_id]
            user_ev_map = {e.event_id: e for e in user_events}
            
            # Determine recurring events for the user as of request_date
            streams = build_recurring_streams(user_events, req.user_id, req.request_date)
            recurring_event_ids = set()
            for s in streams:
                for h_ev in s.historical_evidence:
                    recurring_event_ids.add(h_ev.event_id)

            seen_events_in_changes = set()
            seen_actions_by_event = {}

            for item in sc_items:
                sc_parts = item.split(':')
                action = sc_parts[0].strip()
                if action not in {'stop', 'reduce_to'}:
                    errors.append(f"Rule 13 Violation [{r_id}]: Invalid spending change action '{action}' in '{item}'.")
                    continue

                ev_id = sc_parts[1].strip() if len(sc_parts) > 1 else ''
                if not ev_id:
                    errors.append(f"Rule 13 Violation [{r_id}]: Missing event_id in spending change '{item}'.")
                    continue

                # Mutual exclusivity & duplicate check across all spending changes
                if ev_id in seen_events_in_changes:
                    errors.append(f"Rule 13 Violation [{r_id}]: Event '{ev_id}' appears more than once in spending changes ('{d.spending_changes_needed}').")
                seen_events_in_changes.add(ev_id)
                seen_actions_by_event.setdefault(ev_id, []).append(action)

                # Event existence & user ownership
                if ev_id not in user_ev_map:
                    errors.append(f"Rule 13 Violation [{r_id}]: Referenced event '{ev_id}' does not exist or does not belong to user '{req.user_id}'.")
                    continue

                ev = user_ev_map[ev_id]

                # Event must be a debit expense
                if ev.direction != 'debit':
                    errors.append(f"Rule 13 Violation [{r_id}]: Referenced event '{ev_id}' direction is '{ev.direction}', must be 'debit'.")

                # Event must be recurring
                if not ev.is_recurring and ev_id not in recurring_event_ids:
                    errors.append(f"Rule 13 Violation [{r_id}]: Referenced event '{ev_id}' is not a recurring event.")

                # Event must be flexible
                if ev.flexibility not in {'stoppable', 'reducible', 'reducible_or_stoppable'}:
                    errors.append(f"Rule 13 Violation [{r_id}]: Referenced event '{ev_id}' flexibility is '{ev.flexibility}', not flexible.")

                # Event category must NOT be protected
                if prof and ev.category in prof.expense_categories_to_protect:
                    errors.append(f"Rule 13 Violation [{r_id}]: Referenced event '{ev_id}' in category '{ev.category}' is protected.")

                # STOP specific checks
                if action == 'stop':
                    if len(sc_parts) != 2:
                        errors.append(f"Rule 13 Violation [{r_id}]: Invalid stop syntax '{item}', expected 'stop:<event_id>'.")
                    if ev.flexibility not in {'stoppable', 'reducible_or_stoppable'}:
                        errors.append(f"Rule 13 Violation [{r_id}]: Event '{ev_id}' flexibility '{ev.flexibility}' does not permit 'stop'.")
                    if prof and ev.category not in prof.expense_categories_to_stop:
                        errors.append(f"Rule 13 Violation [{r_id}]: Event '{ev_id}' category '{ev.category}' is not in user expense_categories_to_stop ({prof.expense_categories_to_stop}).")

                # REDUCE_TO specific checks
                elif action == 'reduce_to':
                    if len(sc_parts) != 3:
                        errors.append(f"Rule 13 Violation [{r_id}]: Invalid reduce_to syntax '{item}', expected 'reduce_to:<event_id>:<new_amount>'.")
                        continue
                    
                    if ev.flexibility not in {'reducible', 'reducible_or_stoppable'}:
                        errors.append(f"Rule 13 Violation [{r_id}]: Event '{ev_id}' flexibility '{ev.flexibility}' does not permit 'reduce_to'.")
                    if prof and ev.category not in prof.expense_categories_to_reduce:
                        errors.append(f"Rule 13 Violation [{r_id}]: Event '{ev_id}' category '{ev.category}' is not in user expense_categories_to_reduce ({prof.expense_categories_to_reduce}).")

                    # Validate new_amount
                    try:
                        new_amount = Decimal(sc_parts[2].strip())
                    except Exception as e:
                        errors.append(f"Rule 13 Violation [{r_id}]: reduce_to new_amount '{sc_parts[2]}' is not numeric: {e}")
                        continue

                    # new_amount must not be negative
                    if new_amount < Decimal('0'):
                        errors.append(f"Rule 13 Violation [{r_id}]: reduce_to new_amount {new_amount} cannot be negative.")

                    # new_amount must be < original amount
                    orig_amount = ev.amount if ev.amount is not None else Decimal('0')
                    if new_amount >= orig_amount:
                        errors.append(f"Rule 13 Violation [{r_id}]: reduce_to new_amount {new_amount} must be strictly less than original amount {orig_amount}.")

                    # new_amount must be >= minimum_allowed_amount when supplied
                    if ev.minimum_allowed_amount is not None and new_amount < ev.minimum_allowed_amount:
                        errors.append(f"Rule 13 Violation [{r_id}]: reduce_to new_amount {new_amount} is below event minimum_allowed_amount {ev.minimum_allowed_amount}.")

        # 14. earliest_date_for_full_payment follows the rules
        # 15. affordable_now uses request_date
        if d.affordability_status == 'affordable_now':
            if d.earliest_date_for_full_payment != req.request_date:
                errors.append(f"Rule 15 Violation [{r_id}]: affordable_now must have earliest_date_for_full_payment equal to request_date ({req.request_date}), got {d.earliest_date_for_full_payment}.")
        elif d.affordability_status == 'affordable_later':
            if not d.earliest_date_for_full_payment or d.earliest_date_for_full_payment <= req.request_date:
                errors.append(f"Rule 14 Violation [{r_id}]: affordable_later must have earliest_date_for_full_payment > request_date ({req.request_date}), got {d.earliest_date_for_full_payment}.")

        # 17. no required field is silently invented (empty strings or None)
        if not d.decision_explanation or not d.decision_explanation.strip():
            errors.append(f"Rule 17 Violation [{r_id}]: Missing decision_explanation.")

    return errors
