<#
.SYNOPSIS
Envoie le site en ligne (GitHub Pages), après comparaison avec la version précédente et sauvegarde.

.DESCRIPTION
1. Compare la nouvelle version des résultats à la dernière publiée (outils\comparer_versions.py). Si un problème
   bloquant apparaît, rien n'est envoyé. Si des écarts sont à regarder, rien n'est envoyé non plus tant que Lucas ne
   relance pas avec -Valider après avoir lu le compte rendu (donnees\journaux\comparaison_...md).
2. Garde une copie du site envoyé dans donnees\sauvegardes\ (les huit dernières).
3. Prépare et vérifie le code public (outils\preparer_code_public.py --suivi, dépôt permanent donnees\code_public),
   puis l'envoie dans la branche « main » du dépôt GitHub, avant le site, pour que GitHub la montre en premier. Un
   commit n'y est ajouté que si le code a changé.
4. Copie dans un dossier temporaire les seules pages publiques (sans les prototypes ni les maquettes), puis les envoie
   dans la branche « site » du dépôt GitHub. Cette branche est remplacée à chaque envoi, son historique n'est pas gardé.

.PARAMETER Adresse
Première fois seulement, adresse du dépôt GitHub (https://github.com/pseudo/nom.git).
.PARAMETER Courriel
Première fois seulement, adresse anonyme GitHub (nombre+pseudo@users.noreply.github.com).
.PARAMETER Domaine
Facultatif, nom de domaine du site (par exemple ubicura.fr).
.PARAMETER Valider
Publie malgré des écarts « à regarder », après lecture du compte rendu. Jamais en cas de problème bloquant.
.PARAMETER Restaurer
Chemin d'une sauvegarde (donnees\sauvegardes\site_....zip) à remettre en ligne.
.PARAMETER Essai
Fait tout sauf l'envoi, pour vérifier.
#>
param([string]$Adresse, [string]$Courriel, [string]$Domaine, [switch]$Valider, [string]$Restaurer, [switch]$Essai)

# « Continue », car Windows PowerShell 5.1 traite tout message d'erreur de git ou de Python comme une erreur bloquante
$ErrorActionPreference = "Continue"
$racine = Split-Path -Parent $PSScriptRoot
Set-Location $racine
$python = Join-Path $racine ".venv\Scripts\python.exe"
$config = Join-Path $racine "donnees\publication.json"
$sauvegardes = Join-Path $racine "donnees\sauvegardes"
$journaux = Join-Path $racine "donnees\journaux"
New-Item -ItemType Directory -Force -Path $sauvegardes, $journaux | Out-Null
$log = Join-Path $journaux ("publication_" + (Get-Date -Format "yyyy-MM-dd_HHmm") + ".log")
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Ecrire([string]$texte) {
    $ligne = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $texte
    Write-Host $ligne
    Add-Content -Path $log -Value $ligne -Encoding UTF8
}
function Prevenir([string]$texte) {
    # fenêtre d'avertissement, pour que Lucas voie qu'une décision l'attend
    try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($texte, "Ubi Cura, publication") | Out-Null } catch {}
}

# réglages, gardés d'une fois sur l'autre
$c = @{}
if (Test-Path $config) { (Get-Content $config -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $c[$_.Name] = $_.Value } }
if ($Adresse) { $c["adresse"] = $Adresse }
if ($Courriel) { $c["courriel"] = $Courriel }
if ($Domaine) { $c["domaine"] = $Domaine }
if (-not $c["adresse"] -or -not $c["courriel"]) {
    Ecrire "Adresse du dépôt ou adresse anonyme manquante, rien n'est envoyé (tutoriel 06, mise en ligne)."
    exit 1
}
if ($c["courriel"] -notmatch "@users\.noreply\.github\.com$") {
    Ecrire "L'adresse $($c["courriel"]) n'est pas l'adresse anonyme de GitHub, rien n'est envoyé."
    exit 1
}
$c | ConvertTo-Json | Set-Content -Path $config -Encoding UTF8

$version = (Get-ChildItem (Join-Path $racine "resultats") -Directory | Where-Object { $_.Name -match "^20" -and (Test-Path (Join-Path $_.FullName "site_data.json")) } | Sort-Object Name | Select-Object -Last 1).Name
$temp = Join-Path $env:TEMP "offre_soins_publication"
if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
New-Item -ItemType Directory -Force -Path $temp | Out-Null

if ($Restaurer) {
    Ecrire "Restauration de la sauvegarde $Restaurer."
    Expand-Archive -Path $Restaurer -DestinationPath $temp -Force
    $libelle = "restauration de " + [IO.Path]::GetFileNameWithoutExtension($Restaurer)
} else {
    Ecrire "Comparaison de la version $version avec la dernière publiée."
    $sortie = & $python outils\comparer_versions.py 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    foreach ($l in $sortie) { if ($l.Trim()) { Add-Content -Path $log -Value $l -Encoding UTF8 } }
    $compte = ($sortie | Where-Object { $_ -match "^Compte rendu" } | Select-Object -Last 1)
    if ($code -eq 20) {
        Ecrire "Problème bloquant relevé, rien n'est envoyé. $compte"
        Prevenir "La nouvelle version présente un problème bloquant. Rien n'a été mis en ligne.`n`n$compte"
        exit 1
    }
    if ($code -eq 10 -and -not $Valider) {
        Ecrire "Des écarts sont à regarder, rien n'est envoyé. Après lecture, relancer avec -Valider. $compte"
        Prevenir "Des écarts sont à regarder avant de publier. Rien n'a été mis en ligne.`n`nLire le compte rendu, puis relancer la publication avec -Valider (tutoriel 06).`n`n$compte"
        exit 1
    }
    if (-not $c["premiere_version"]) {
        # première mise en ligne, le site ne garde que les rapports à partir de cette version
        $c["premiere_version"] = $version
        $c | ConvertTo-Json | Set-Content -Path $config -Encoding UTF8
        Ecrire "Première mise en ligne, le site est refait avec les seuls rapports à partir de la version $version."
        & $python -m pipeline.site 2>&1 | Out-Null
    }
    Ecrire "Copie des pages publiques."
    robocopy (Join-Path $racine "site") $temp /E /XD prototype prototype2 prototype3 prototype4 maquettes /NFL /NDL /NJH /NJS /NP | Out-Null
    $zip = Join-Path $sauvegardes ("site_" + $version + "_" + (Get-Date -Format "yyyyMMdd_HHmm") + ".zip")
    Compress-Archive -Path (Join-Path $temp "*") -DestinationPath $zip -Force
    Ecrire "Sauvegarde, $zip"
    Get-ChildItem $sauvegardes -Filter "site_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 8 | Remove-Item -Force
    $libelle = "version $version"
}

# code public, envoyé avant le site sur la branche main, celle que GitHub montre en arrivant sur le dépôt. Lors de la
# toute première publication, un problème sur le code arrête tout. Ensuite, le site part quand même et une fenêtre
# prévient.
if (-not $Restaurer) {
    Ecrire "Préparation et vérification du code public."
    $sortieCode = & $python outils\preparer_code_public.py --suivi 2>&1 | ForEach-Object { "$_" }
    $codeCode = $LASTEXITCODE
    foreach ($l in $sortieCode) { if ($l.Trim()) { Add-Content -Path $log -Value $l -Encoding UTF8 } }
    $depotCode = Join-Path $racine "donnees\code_public"
    if ($codeCode -ne 0) {
        Ecrire "Le code public présente un problème bloquant, il n'est pas envoyé. Voir $log"
        if (-not $c["version"]) { Prevenir "Le code public présente un problème bloquant. Rien n'a été mis en ligne.`n`nVoir $log"; exit 1 }
        Prevenir "Le code public présente un problème bloquant et n'est pas envoyé. Le site est tout de même publié.`n`nVoir $log"
    } elseif ($Essai) {
        Ecrire "Essai, code public prêt dans $depotCode, rien n'est envoyé."
    } else {
        Ecrire "Envoi du code vers $($c["adresse"]), branche main."
        git -C $depotCode push --quiet $c["adresse"] main:main
        if ($LASTEXITCODE -ne 0) {
            Ecrire "L'envoi du code a échoué (connexion, identifiants, ou branche main modifiée directement sur GitHub)."
            if (-not $c["version"]) { Prevenir "L'envoi du code a échoué. Rien n'a été mis en ligne.`n`nVoir $log"; exit 1 }
            Prevenir "L'envoi du code a échoué. Le site est tout de même publié.`n`nVoir $log"
        }
    }
}

New-Item -ItemType File -Force -Path (Join-Path $temp ".nojekyll") | Out-Null
if ($c["domaine"]) { Set-Content -Path (Join-Path $temp "CNAME") -Value $c["domaine"] -Encoding ASCII -NoNewline }

Push-Location $temp
try {
    git init --quiet --initial-branch=site 2>$null
    if ($LASTEXITCODE -ne 0) { git init --quiet; git checkout --quiet -b site }
    git config core.autocrlf false
    git add --all
    git -c user.name="Lucas Pithon" -c user.email="$($c["courriel"])" commit --quiet -m "Site, $libelle"
    if ($Essai) { Ecrire "Essai, tout est prêt dans $temp, rien n'est envoyé."; exit 0 }
    Ecrire "Envoi vers $($c["adresse"]), branche site."
    git push --force --quiet $c["adresse"] site:site
    if ($LASTEXITCODE -ne 0) { Ecrire "L'envoi a échoué (connexion, identifiants ou adresse du dépôt)."; Prevenir "L'envoi du site a échoué. Voir $log"; exit 1 }
} finally { Pop-Location }

$c["version"] = $version; $c["date"] = (Get-Date -Format s)
if ($Restaurer) { $c["version"] = $libelle }
else {
    # versions mises en ligne, seules gardées par le site avec la dernière (pipeline/site.py)
    $vp = @(); if ($c["versions_publiees"]) { $vp = @($c["versions_publiees"]) }
    $c["versions_publiees"] = @(($vp + $version) | Sort-Object -Unique)
}
$c | ConvertTo-Json | Set-Content -Path $config -Encoding UTF8
Ecrire "Site en ligne, $libelle. Il apparaît sur GitHub Pages en une ou deux minutes."
exit 0
