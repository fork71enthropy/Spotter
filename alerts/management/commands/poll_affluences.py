import time

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from alerts.affluences_client import AffluencesError, fetch_availability, libres_dans_la_plage
from alerts.models import WatchedSlot

# 2-3 minutes : un compromis entre "réactif" et "respectueux" du serveur
# d'un site externe qu'on ne contrôle pas (voir discussion avec l'utilisateur).
POLL_INTERVAL_SECONDS = 150


class Command(BaseCommand):
    help = "Surveille l'API Affluences et notifie les WatchedSlot dont un créneau vient de se libérer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="N'exécute qu'un seul passage (pratique pour tester), au lieu de boucler indéfiniment.",
        )

    def handle(self, *args, **options):
        while True:
            self.run_once()
            if options["once"]:
                break
            time.sleep(POLL_INTERVAL_SECONDS)

    def run_once(self):
        today = dj_timezone.localdate()
        actifs = WatchedSlot.objects.filter(
            est_actif=True, notifie_le__isnull=True, date_cible__gte=today
        ).select_related("utilisateur")

        # On groupe par (site_id, date_cible) pour ne faire qu'UN SEUL appel
        # API par site/jour, peu importe combien d'utilisateurs surveillent
        # ce jour-là -> c'est ce qui rend le polling scalable.
        par_site_et_date = {}
        for watch in actifs:
            par_site_et_date.setdefault((watch.site_id, watch.date_cible), []).append(watch)

        for (site_id, date_cible), watches in par_site_et_date.items():
            try:
                rooms = fetch_availability(site_id, date_cible.isoformat())
            except AffluencesError as exc:
                self.stderr.write(self.style.WARNING(str(exc)))
                continue

            for watch in watches:
                libres = libres_dans_la_plage(rooms, watch.resource_id, watch.heure_debut, watch.heure_fin)
                if libres:
                    watch.notifie_le = dj_timezone.now()
                    watch.save(update_fields=["notifie_le"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"ALERTE : {watch.utilisateur.email} -> "
                            f"{watch.resource_nom} libre à {', '.join(libres)}"
                        )
                    )