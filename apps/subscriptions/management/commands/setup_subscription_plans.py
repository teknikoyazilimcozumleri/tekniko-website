"""
Create one Iyzico subscription product and a pricing plan for each SubscriptionPlan
that does not yet have iyzico_pricing_plan_reference_code.
Run once after deploy or when adding new plans: python manage.py setup_subscription_plans
"""
from django.core.management.base import BaseCommand

from apps.subscriptions.iyzico_subscription_client import (
    create_pricing_plan,
    create_product,
    list_pricing_plans,
    list_products,
)
from apps.subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Create Iyzico subscription product and pricing plans for SubscriptionPlan records that lack reference codes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--product-name",
            default="Template Abonelik Paketleri",
            help="Name of the single Iyzico product (used for all plans).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be done, do not call Iyzico.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="On failure, print full Iyzico response.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        product_name = options["product_name"]

        plans_needing_setup = list(SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "id"))
        if not plans_needing_setup:
            self.stdout.write("No active SubscriptionPlan records found.")
            return

        need_product = not any(p.iyzico_product_reference_code for p in plans_needing_setup)
        need_plans = [p for p in plans_needing_setup if not p.iyzico_pricing_plan_reference_code]

        if not need_plans:
            self.stdout.write(self.style.SUCCESS("All plans already have Iyzico pricing plan reference codes."))
            return

        if dry_run:
            self.stdout.write(f"Would create product: {product_name}")
            for p in need_plans:
                self.stdout.write(f"  Would create pricing plan for: {p.name} ({p.price} {p.currency}/MONTHLY)")
            return

        product_ref = None
        verbose = options.get("verbose", False)
        if need_product:
            self.stdout.write(f"Creating Iyzico product: {product_name}")
            product_ref, data = create_product(product_name, description=product_name)
            if not product_ref:
                err_code = str(data.get("errorCode") or "")
                if err_code == "201001":
                    self.stdout.write(self.style.WARNING("Product already exists (201001), fetching existing product..."))
                    items, list_data = list_products()
                    if items:
                        for p in items:
                            if (p.get("name") or "").strip() == (product_name or "").strip():
                                product_ref = p.get("referenceCode")
                                break
                        if not product_ref and items:
                            product_ref = items[0].get("referenceCode")
                    if product_ref:
                        self.stdout.write(self.style.SUCCESS(f"Using existing product reference: {product_ref}"))
                    else:
                        self.stderr.write(
                            self.style.ERROR("Product exists but could not list products. Check Iyzico panel for product reference.")
                        )
                        if verbose and list_data:
                            import json
                            self.stderr.write(self.style.WARNING("List response: " + json.dumps(list_data, indent=2, ensure_ascii=False)))
                        return
                else:
                    err_msg = data.get("errorMessage") or "Sistem hatası"
                    self.stderr.write(self.style.ERROR(f"Failed to create product: {err_msg}" + (f" (code: {err_code})" if err_code else "")))
                    if verbose:
                        import json
                        self.stderr.write(self.style.WARNING("Full response: " + json.dumps(data, indent=2, ensure_ascii=False)))
                    if err_code == "100001":
                        self.stderr.write("")
                        self.stderr.write(
                            self.style.WARNING(
                                "100001: Subscription may be disabled for your account. "
                                "Contact Iyzico support (entegrasyon@iyzico.com) to enable Subscription."
                            )
                        )
                    return
            else:
                self.stdout.write(self.style.SUCCESS(f"Product reference: {product_ref}"))
        else:
            product_ref = next(
                (p.iyzico_product_reference_code for p in plans_needing_setup if p.iyzico_product_reference_code),
                None,
            )
            if not product_ref:
                self.stderr.write(self.style.ERROR("No product reference available and could not create one."))
                return

        existing_plans_cache = None
        for plan in need_plans:
            self.stdout.write(f"Creating pricing plan for: {plan.name} ({plan.price} {plan.currency})")
            ref, data = create_pricing_plan(
                product_ref,
                name=plan.name,
                price=plan.price,
                currency_code=plan.currency,
            )
            if not ref:
                err_code = str(data.get("errorCode") or "")
                err_msg = data.get("errorMessage") or "Sistem hatası"
                if err_code == "201051":
                    self.stdout.write(self.style.WARNING("  Plan already exists (201051), fetching existing plans..."))
                    if existing_plans_cache is None:
                        existing_plans_cache, _ = list_pricing_plans(product_ref)
                    items = existing_plans_cache or []
                    for item in items:
                        item_name = (item.get("name") or "").strip()
                        item_price = item.get("price")
                        if item_name == (plan.name or "").strip():
                            ref = item.get("referenceCode")
                            break
                        if item_price is not None and str(item_price) == str(plan.price):
                            ref = item.get("referenceCode")
                            break
                    if not ref and items:
                        ref = items[0].get("referenceCode")
                if not ref:
                    self.stderr.write(self.style.ERROR(f"  Failed: {err_msg}" + (f" (code: {err_code})" if err_code else "")))
                    if verbose:
                        import json
                        self.stderr.write(self.style.WARNING("  Full response: " + json.dumps(data, indent=2, ensure_ascii=False)))
                    continue
                else:
                    self.stdout.write(self.style.SUCCESS(f"  Using existing plan reference: {ref}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  Plan reference: {ref}"))
            plan.iyzico_product_reference_code = product_ref
            plan.iyzico_pricing_plan_reference_code = ref
            plan.save(update_fields=["iyzico_product_reference_code", "iyzico_pricing_plan_reference_code"])

        self.stdout.write(self.style.SUCCESS("Done."))
