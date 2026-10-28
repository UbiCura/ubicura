<#
.SYNOPSIS
Mise à jour des données, des résultats et du site, à lancer à la main ou par une tâche planifiée Windows.

.DESCRIPTION
1. Ne fait rien si la dernière vérification complète date de moins de -JoursMin jours (6 par défaut), sauf avec -Forcer.
2. Demande à chaque producteur si une nouvelle version existe (python run.py --verifier), sans rien télécharger.
3. Si au moins une source a changé, lance la chaîne complète (python run.py). Seules les sources modifiées sont
   retéléchargées, puis les résultats, les rapports, le site et le journal des mises à jour sont refaits.
4. Vérifie à nouveau après coup que chaque source est bien à jour, puis recalcule une série de chiffres publiés
   depuis les fichiers bruts par un code indépendant (outils\controle_independant.py).
5. Garde un compte rendu de chaque passage dans donnees\journaux\.
6. Chaque jour, regarde sur Zenodo si une nouvelle version des trois dépôts a été publiée (outils\zenodo.py, tutoriel
   07). Si oui, le site est refait pour la citer par son DOI. Une fenêtre rappelle aussi d'archiver une version chaque
   trimestre.
7. Ne met plus rien en ligne de lui-même (décision de Lucas du 26 octobre 2026). Une version refaite et contrôlée est
   comparée à la version en ligne (outils\comparer_versions.py) et signalée dans donneesersion_prete.json, que la
   fenêtre du courrier affiche. Lucas décide de la publication. -Publier reste possible à la main.

.PARAMETER Simuler
Fait seulement la vérification et dit ce qui serait fait, sans rien télécharger ni recalculer.

.PARAMETER Publier
Après une mise à jour réussie et contrôlée, envoie le site en ligne (outils\publier.ps1, tutoriel 06).

.PARAMETER Forcer
Ignore le délai minimal entre deux vérifications.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File D:\offre_soins\outils\mise_a_jour.ps1 -Simuler
#>
param([switch]$Forcer, [switch]$Simuler, [switch]$Publier, [int]$JoursMin = 6)

$ErrorActionPreference = "Continue"
$racine = Split-Path -Parent $PSScriptRoot
Set-Location $racine
$python = Join-Path $racine ".venv\Scripts\python.exe"
$etatFichier = Join-Path $racine "donnees\etat_mise_a_jour.json"
$verrou = Join-Path $racine "donnees\mise_a_jour.verrou"
$journaux = Join-Path $racine "donnees\journaux"
New-Item -ItemType Directory -Force -Path $journaux | Out-Null
$log = Join-Path $journaux ("mise_a_jour_" + (Get-Date -Format "yyyy-MM-dd_HHmm") + ".log")
$env:PYTHONUTF8 = "1"
# sorties de Python lues en UTF-8, y compris quand le script est lancé par le Planificateur de tâches
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Ecrire([string]$texte) {
    $ligne = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $texte
    Write-Host $ligne
    Add-Content -Path $log -Value $ligne -Encoding UTF8
}
function Prevenir([string]$texte) {
    # fenêtre d'avertissement quand la mise à jour s'arrête, pour que Lucas le sache sans ouvrir les comptes rendus
    try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($texte, "Ubi Cura, mise à jour") | Out-Null } catch {}
}

function PublierSite {
    Ecrire "Publication du site, après comparaison avec la version en ligne."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "publier.ps1") | Out-Host
    return $LASTEXITCODE
}

function VersionPrete([string]$motif) {
    # version refaite et contrôlée, comparée à la version en ligne et signalée à Lucas (fenêtre du courrier), sans envoi
    $sortie = & $python outils\comparer_versions.py 2>&1 | ForEach-Object { "$_" }
    $codeC = $LASTEXITCODE
    $cr = ($sortie | Where-Object { $_ -match "^Compte rendu, " } | Select-Object -Last 1) -replace "^Compte rendu, ", ""
    $res = Get-ChildItem (Join-Path $racine "resultats") -Directory | Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } | Sort-Object Name | Select-Object -Last 1
    $etatC = @{0 = "rien d'anormal"; 10 = "des écarts à regarder"; 20 = "un problème bloquant"}[$codeC]
    if (-not $etatC) { $etatC = "comparaison impossible (code $codeC)" }
    @{ resultats = $res.Name; motif = $motif; code_comparaison = $codeC; comparaison = $etatC; compte_rendu = $cr;
       preparee_le = (Get-Date -Format s) } | ConvertTo-Json | Set-Content -Path (Join-Path $racine "donneesersion_prete.json") -Encoding UTF8
    Ecrire "Nouvelle version prête ($($res.Name), $motif), comparaison avec la version en ligne, $etatC. Rien n'est publié sans Lucas."
}

function Verifier {
    # renvoie le code de sortie de la vérification (0 à jour, 10 à mettre à jour, 20 incomplète)
    $sortie = & $python run.py --verifier 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    foreach ($l in $sortie) { if ($l -notmatch " INFO " -and $l.Trim()) { Ecrire $l } }
    return $code
}

function Enregistrer([hashtable]$changements) {
    $etat = @{}
    if (Test-Path $etatFichier) {
        $lu = Get-Content $etatFichier -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($p in $lu.PSObject.Properties) { $etat[$p.Name] = $p.Value }
    }
    foreach ($k in $changements.Keys) { $etat[$k] = $changements[$k] }
    $etat | ConvertTo-Json | Set-Content -Path $etatFichier -Encoding UTF8
}

if (-not (Test-Path $python)) { Ecrire "Environnement Python introuvable ($python)."; Prevenir "La mise à jour n'a pas pu démarrer, l'environnement Python est introuvable.`n`nVoir $log"; exit 1 }

# une seule mise à jour à la fois (par exemple un lancement à la main pendant celui de la tâche planifiée)
if (Test-Path $verrou) {
    $pid0 = Get-Content $verrou -ErrorAction SilentlyContinue
    if ($pid0 -and (Get-Process -Id $pid0 -ErrorAction SilentlyContinue)) { Ecrire "Une mise à jour est déjà en cours (processus $pid0)."; exit 0 }
}
Set-Content -Path $verrou -Value $PID

try {
    # nouvelle version archivée sur Zenodo, constatée chaque jour (code 10), sans clé rangée rien n'est fait (code 20)
    if (-not $Simuler) {
        $sortieZ = & $python outils\zenodo.py constater --discret 2>&1 | ForEach-Object { "$_" }
        $codeZ = $LASTEXITCODE
        if ($codeZ -eq 10 -or $codeZ -eq 1) { foreach ($l in $sortieZ) { if ($l.Trim()) { Ecrire $l } } }
        if ($codeZ -eq 10) {
            Ecrire "Reconstruction du site pour citer la version archivée sur Zenodo."
            & $python -m pipeline.site 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Ecrire "La reconstruction du site a échoué, voir donnees\execution.log."
            } elseif ($Publier) {
                if ((PublierSite) -ne 0) { Ecrire "Site non publié, voir le compte rendu de publication dans donnees\journaux." }
                else { & $python outils\zenodo.py site-refait | Out-Null; Ecrire "Site publié, il cite la version archivée sur Zenodo." }
            } else { & $python outils\zenodo.py site-refait | Out-Null; VersionPrete "site refait pour citer la version archivée sur Zenodo" }
        }
    }

    # rappel trimestriel d'archivage sur Zenodo (tutoriel 07), au plus une fois par semaine tant que ce n'est pas fait
    if (-not $Simuler) {
        $rappel = (& $python outils\zenodo.py rappel 2>&1 | ForEach-Object { "$_" }) -join " "
        if ($LASTEXITCODE -eq 10) {
            Ecrire $rappel
            Prevenir ("Archivage trimestriel sur Zenodo.`n`n" + $rappel + "`n`nCommande à lancer dans PowerShell`ncd D:\offre_soins`n.\.venv\Scripts\python.exe outils\zenodo.py preparer")
        }
    }

    if (-not $Forcer -and -not $Simuler -and (Test-Path $etatFichier)) {
        $etat = Get-Content $etatFichier -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($etat.derniere_verification) {
            $jours = ((Get-Date) - [datetime]$etat.derniere_verification).TotalDays
            if ($jours -lt $JoursMin) {
                Ecrire ("Dernière vérification complète il y a {0:N1} jours, moins de {1} jours, rien à faire." -f $jours, $JoursMin)
                exit 0
            }
        }
    }

    Ecrire "Vérification des sources auprès des producteurs, sans téléchargement."
    $code = Verifier
    if ($code -eq 0) {
        Ecrire "Toutes les sources sont à jour, aucun recalcul nécessaire."
        if (-not $Simuler) { Enregistrer @{ derniere_verification = (Get-Date -Format s); dernier_resultat = "à jour" } }
        exit 0
    }
    if ($code -eq 20) {
        Ecrire "Vérification incomplète (connexion ou producteur injoignable). Nouvel essai au prochain lancement."
        exit 0
    }
    if ($code -ne 10) { Ecrire "La vérification a échoué (code $code), voir donnees\execution.log."; exit 1 }

    if ($Simuler) { Ecrire "Simulation, la chaîne complète serait lancée pour reprendre les sources signalées."; exit 0 }

    Ecrire "Mise à jour, chaîne complète (téléchargement des seules sources modifiées, calculs, rapports, site)."
    $debut = Get-Date
    & $python run.py
    $codeRun = $LASTEXITCODE
    $minutes = [math]::Round(((Get-Date) - $debut).TotalMinutes, 1)
    if ($codeRun -ne 0) {
        Ecrire "La chaîne complète s'est arrêtée en erreur après $minutes min (code $codeRun), voir donnees\execution.log."
        Enregistrer @{ dernier_resultat = "erreur"; derniere_erreur = (Get-Date -Format s) }
        Prevenir "La mise à jour s'est arrêtée en erreur. Rien n'a été publié, le site en ligne n'a pas changé.`n`nVoir $log"
        exit 1
    }
    Ecrire "Chaîne complète terminée en $minutes min."

    Ecrire "Contrôle après coup, chaque source doit maintenant être à jour."
    $apres = Verifier
    if ($apres -eq 0) {
        Ecrire "Contrôle réussi, toutes les sources sont à jour."
        Enregistrer @{ derniere_verification = (Get-Date -Format s); derniere_mise_a_jour = (Get-Date -Format s); dernier_resultat = "mis à jour" }
    } elseif ($apres -eq 10) {
        Ecrire "Attention, une source signalée n'a pas été reprise. Voir donnees\verification.json et donnees\execution.log."
        Enregistrer @{ derniere_mise_a_jour = (Get-Date -Format s); dernier_resultat = "mise à jour partielle" }
        Prevenir "Une source signalée n'a pas été reprise. Rien n'a été publié, le site en ligne n'a pas changé.`n`nVoir $log"
        exit 1
    } else {
        Ecrire "Contrôle après coup incomplet (producteur injoignable), la mise à jour elle-même a réussi."
        Enregistrer @{ derniere_mise_a_jour = (Get-Date -Format s); dernier_resultat = "mis à jour, contrôle incomplet" }
    }
    Ecrire "Contrôle indépendant des chiffres publiés, recalculés depuis les fichiers bruts."
    $sortie = & $python outils\controle_independant.py 2>&1 | ForEach-Object { "$_" }
    $codeCtrl = $LASTEXITCODE
    foreach ($l in $sortie) { if ($l -match "^.CART|conformes|sultats contr") { Ecrire $l } }
    if ($codeCtrl -ne 0) {
        Ecrire "Attention, le contrôle indépendant relève au moins un écart. Ne pas publier cette version avant vérification."
        Enregistrer @{ dernier_controle = "écart" }
        Prevenir "Le contrôle indépendant relève un écart dans les chiffres. Rien n'a été publié, le site en ligne n'a pas changé.`n`nVoir $log"
        exit 1
    }
    Enregistrer @{ dernier_controle = "conforme" }
    if ($Publier) {
        if ((PublierSite) -ne 0) { Ecrire "Site non publié, voir le compte rendu de publication dans donnees\journaux."; exit 1 }
    } else { VersionPrete "nouvelle version d'au moins une source" }
    exit 0
}
finally {
    Remove-Item -Path $verrou -ErrorAction SilentlyContinue
    Ecrire "Compte rendu, $log"
}
