"""Point d'entrée.  python run.py            exécution complète
                   python run.py --hors-ligne   réutilise les fichiers déjà téléchargés
                   python run.py --rafraichir   force le retéléchargement
                   python run.py --inspecter    affiche les colonnes des fichiers téléchargés
                   python run.py --sans-spatial saute le calcul des voisinages (plus rapide)
                   python run.py --verifier     demande à chaque producteur si une nouvelle version existe, sans rien
                                                télécharger (code de sortie 0 à jour, 10 à mettre à jour, 20 incomplet)"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date

import numpy as np

from pipeline import analyses, build, concordance, config, evolution, export, lieux, mises_a_jour, site
from pipeline.sources import (acces_route, ameli, ameli_acces, ameli_ald, apl, caf, drees_demographie, drees_isd, sae, complements,
                              has_certification, sirene, finess, insee, insee_estimations, odisse, optionnels,
                              referentiel, ror, rpps)
from pipeline.util import JOURNAL, detecter_separateur, premiere_ligne


def inspecter():
    for p in sorted(config.BRUT.glob("*")):
        if p.suffix in (".txt", ".csv"):
            enc = "latin-1" if "historique" in p.name else "utf-8-sig"
            l = premiere_ligne(p, enc)
            print(f"\n{p.name}  ({p.stat().st_size / 1e6:.0f} Mo, séparateur « {detecter_separateur(l)} »)")
            for c in l.split(detecter_separateur(l)):
                print("   ", c)


def main(argv=None):
    a = argparse.ArgumentParser(description="Collecte et analyse de l'offre de soins en France")
    a.add_argument("--hors-ligne", action="store_true")
    a.add_argument("--rafraichir", action="store_true")
    a.add_argument("--inspecter", action="store_true")
    a.add_argument("--sans-spatial", action="store_true")
    a.add_argument("--date", help="date à utiliser pour le dossier de résultats (AAAA-MM-JJ)")
    a.add_argument("--sans-pdf", action="store_true", help="ne pas imprimer les rapports en PDF")
    a.add_argument("--verifier", action="store_true",
                   help="vérifier auprès des producteurs si une source a changé, sans rien télécharger")
    args = a.parse_args(argv)
    for d in (config.BRUT, config.INTER, config.RESULTATS):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(config.DONNEES / "execution.log", encoding="utf-8")])
    if args.inspecter:
        inspecter()
        return
    if args.verifier:
        from pipeline import verification
        sys.exit(verification.afficher(verification.verifier()))
    t0 = time.time()
    hl, rf = args.hors_ligne, args.rafraichir

    ref = referentiel.charger(hl, rf)
    fichiers = rpps.telecharger_tout(hl, rf)
    act, professions = rpps.lire_activites(fichiers, ref)
    act.to_parquet(config.INTER / "rpps_activites.parquet", index=False)
    ids_psy = set(act.loc[act["prof"] == "psychologue", "id"])
    diplomes = rpps.diplomes_psychologues(fichiers, ids_psy)
    fin = finess.charger(hl, rf)
    ins = insee.charger(ref, hl, rf)
    # bases complémentaires (descripteurs versionnés dans complements/) et Assurance Maladie
    ctx, indicateurs = complements.charger(ref, ins["contexte"] if ins else None, hl, rf)
    am = ameli.charger(ref, hl, rf)
    spf = odisse.charger(hl, rf)
    acc = ameli_acces.charger(ref, hl, rf)
    isd = drees_isd.charger(hl, rf)
    hop = sae.charger(ref, ctx.get("dep"), hl, rf)
    ald = ameli_ald.charger(hl, rf)
    allo = caf.charger(ref, hl, rf)
    for src in (am, spf, acc, isd, hop, ald, allo):
        if src:
            for niv, t in src["contexte"].items():
                ctx[niv] = ctx[niv].join(t, how="left") if niv in ctx else t
            indicateurs += src["defs"]
    contexte = {"contexte": ctx, "millesimes": ins["millesimes"] if ins else {}, "indicateurs": indicateurs,
                "ameli": am, "odisse": spf, "ameli_acces": acc, "drees_isd": isd, "sae": hop, "ald": ald, "caf": allo} if (ins or indicateurs) else None
    # temps de trajet par la route (INSEE) et accessibilité officielle (DREES), pour situer nos distances
    externes = {"acces_route": acces_route.charger(ref, hl, rf), "apl": apl.charger(ref, hl, rf)}
    if contexte:
        contexte.update(externes)
    voisins = None if args.sans_spatial else optionnels.voisinages(ref, hl, rf)
    offres = optionnels.offres_france_travail(ref, hl)
    # lieux de soins, FINESS et ROR réunis sans double compte (version 2, 12 octobre 2026)
    lieux_res = lieux.calculer(ror.charger(hl, rf), fin, act, ref, voisins, hl,
                               has_certification.charger(hl, rf), sirene.charger(hl, rf))
    # lieux pour 100 000 habitants et distances, ajoutés aux indicateurs de contexte pour être croisés
    src_lieux = lieux.indicateurs(lieux_res, ref, ctx) if contexte else None
    if src_lieux:
        for niv, t in src_lieux["contexte"].items():
            ctx[niv] = ctx[niv].join(t, how="left") if niv in ctx else t
        indicateurs += src_lieux["defs"]
    if lieux_res and "epci" in ctx and "revenu_median" in ctx["epci"]:
        lieux_res["escalier"] = lieux.escalier_distances(lieux_res, ref, ctx["epci"]["revenu_median"])
        lieux_res["inegalites"] = lieux.inegalites_distances(lieux_res, ref, ctx["epci"],
                                                             np.random.default_rng(config.GRAINE))
    if lieux_res:
        # sensibilité au niveau de confirmation, charge par CMP (SAE), zones d'éloignement (15 octobre 2026)
        from pipeline import structures_analyses
        structures_analyses.appliquer_tout(lieux_res, ref, (voisins or {}).get("centres"), ctx if contexte else None,
                                           voisins, hop, np.random.default_rng(config.GRAINE))
        lieux_res["concordance_sae"] = lieux.concordance_sae(lieux_res, hop, ref)
        lieux_res["concordance_etablissements"] = lieux.concordance_etablissements(lieux_res, hop, fin)

    act, professions = build.perimetre_elargi(act, fin, professions)
    agg = build.agreger(act, ref, fin, lieux_res)
    if lieux_res:
        # double éloignement, sans professionnel déclaré et loin d'une structure (besoin des effectifs agrégés)
        try:
            lieux_res["double_eloignement"] = structures_analyses.double_eloignement(agg, lieux_res, ref)
        except Exception as e:  # noqa: BLE001
            logging.exception("double éloignement")
            JOURNAL.note("Structures de soins, double éloignement", "erreur", str(e)[:300])
    # précisions des spécialités surtout salariées, calculées sur cette exécution (version 2, 11 octobre 2026)
    from pipeline import limites as _limites
    _spec = _limites.specialites_salariees(agg.national, professions)
    _limites.completer(_spec)
    JOURNAL.controle("Spécialités médicales dont moins d'un tiers des médecins exercent en libéral",
                     ", ".join(L["nom"].split(",")[0] for L in _spec.values()) or "aucune")
    R = analyses.tout(agg, ref, ctx if contexte else None, voisins, offres, externes)
    # effectifs rapprochés des séries publiées par la DREES (tableau de concordance)
    series = drees_demographie.charger(hl, rf)
    R.update(concordance.calculer(agg, series))
    # évolution de l'offre sur dix ans, séries de la DREES et populations annuelles de l'INSEE
    R.update(evolution.calculer(series, insee_estimations.charger(hl, rf), ref))
    # ce qui a changé depuis l'exécution précédente (jeux de données, effectifs, site), avant l'écriture du journal
    try:
        mises_a_jour.consigner(args.date or date.today().isoformat(), agg.national,
                               dict(zip(professions["id"], professions["libelle"])))
    except Exception as e:  # noqa: BLE001
        logging.exception("journal des mises à jour")
        JOURNAL.note("Journal des mises à jour", "erreur", str(e)[:300])
    out = export.ecrire(agg, ref, professions, contexte, R, diplomes, jour=args.date)
    try:
        dossier_site = site.construire(pdf=not args.sans_pdf)
        logging.info("Site écrit dans %s, ouvrez %s", dossier_site, dossier_site / "index.html")
    except Exception as e:  # noqa: BLE001
        logging.exception("site")
        JOURNAL.note("Site statique", "erreur", str(e)[:300])
    logging.info("Terminé en %.0f s. Ouvrez %s", time.time() - t0, out / "rapport.md")
    erreurs = [e for e in JOURNAL.entrees if e.statut == "erreur"]
    if erreurs:
        logging.warning("%d source(s) en erreur, voir le rapport : %s", len(erreurs), ", ".join(e.source for e in erreurs))


if __name__ == "__main__":
    main()
