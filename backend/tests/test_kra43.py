"""KRA 43 Scopus conference organized — project-created format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA43Tests(WorkflowMixin, PortalTestCase):
    kra = 43
    evidence = ()  # no minimum evidence agreed (D-053)
    payload = staticmethod(lambda: fx.kra43_payload(2))
    expect_text = ("Scopus Conference Organized by the Department", "Project-created report format", "Conference 2 of 2",
                   "KIET-affiliated: 12", "Planned / applied for", "Verified in Scopus", "20% papers of accepted and published papers")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"conference_name": "Only a name"}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("start_date", "end_date", "organizers", "venue", "mode", "coordinators", "delegates", "papers_accepted", "papers_published",
                  "kiet_accepted", "kiet_published", "publication_status", "indexing_status", "brief_report", "outcomes"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("partners", "institutions", "papers_submitted", "publisher", "isbn_issn", "indexing_reference", "doc_checklist"):
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_paper_count_rules_only_at_submission(self):
        p = copy.deepcopy(fx.kra43_payload(1))
        a = p["activities"][0]
        a.update(papers_accepted=10, papers_published=12, kiet_accepted=11, kiet_published=13)
        self.assertEqual(self.errors_for(p, strict=False), {})
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.papers_published"], ["Published papers cannot exceed accepted papers."])
        self.assertEqual(fe["activities.0.kiet_accepted"], ["KIET-affiliated accepted papers cannot exceed accepted papers."])
        a.update(papers_published=8, kiet_accepted=1, kiet_published=1)  # 10% KIET: allowed — the portal does not enforce the 20% condition
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())

    def test_indexing_status_never_implied(self):
        p = copy.deepcopy(fx.kra43_payload(1))
        a = p["activities"][0]
        a["indexing_reference"] = ""
        self.assertEqual(self.errors_for(p)["activities.0.indexing_reference"], ["Required."])  # verified needs a reference
        a.update(indexing_status="Claimed by publisher/organizer", indexing_reference="")
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("<b>Claimed by publisher/organizer</b>", html)
        self.assertNotIn("Verified in Scopus", html)  # "Scopus" in the title does not imply indexing
        self.assertNotIn("%</", html.split("Participation and papers")[1])  # no computed percentage

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=43)}
        self.assertTrue(any("20% papers" in t for t in before.values()))
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=43).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra43"})
