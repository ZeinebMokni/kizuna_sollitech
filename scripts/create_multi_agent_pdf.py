from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUT = Path('output/pdf/qatra_multi_agent_architecture.pdf')
OUT.parent.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor('#123B46')
TEAL = colors.HexColor('#197C8C')
PALE = colors.HexColor('#EEF7F7')
LINE = colors.HexColor('#D4E4E5')
TEXT = colors.HexColor('#25434A')
MUTED = colors.HexColor('#5C7479')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleQA', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=22, leading=27, textColor=NAVY, alignment=1, spaceAfter=8))
styles.add(ParagraphStyle(name='SubQA', parent=styles['Normal'], fontSize=10, leading=14, textColor=MUTED, alignment=1, spaceAfter=14))
styles.add(ParagraphStyle(name='H1QA', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=NAVY, spaceBefore=3, spaceAfter=8))
styles.add(ParagraphStyle(name='H2QA', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=TEAL, spaceBefore=7, spaceAfter=5))
styles.add(ParagraphStyle(name='BodyQA', parent=styles['BodyText'], fontSize=8.5, leading=12, textColor=TEXT, spaceAfter=5))
styles.add(ParagraphStyle(name='CellQA', parent=styles['BodyText'], fontSize=7, leading=9, textColor=TEXT))
styles.add(ParagraphStyle(name='CellBoldQA', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=NAVY))

def P(text, style='BodyQA'):
    return Paragraph(text, styles[style])

def make_table(rows, widths):
    data = [[P(str(c), 'CellBoldQA' if i == 0 else 'CellQA') for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    cmds = [('GRID', (0,0), (-1,-1), .35, LINE), ('BACKGROUND', (0,0), (-1,0), PALE), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]
    for i in range(2, len(rows), 2): cmds.append(('BACKGROUND', (0,i), (-1,i), colors.HexColor('#FAFCFC')))
    t.setStyle(TableStyle(cmds))
    return t

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18*mm, 14*mm, 192*mm, 14*mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 9*mm, 'QATRA - Architecture multi-agent agricole')
    canvas.drawRightString(192*mm, 9*mm, f'Page {doc.page}')
    canvas.restoreState()

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=20*mm)
s = [Spacer(1, 15*mm), P('QATRA', 'TitleQA'), P('Architecture multi-agent agricole', 'TitleQA'), P('Pages, agents, données nécessaires et contrôles de décision pour une exploitation tunisienne connectée.', 'SubQA')]
s += [P('<b>Objectif</b><br/>Observer l environnement, comprendre les causes, proposer des solutions, mesurer l impact et améliorer la ferme sans automatiser aveuglément.', 'BodyQA')]
s += [P('Chaîne de décision', 'H1QA'), make_table([['Observer','Comprendre','Prévoir','Vérifier','Agir','Mesurer'], ['Capteurs, satellite, météo','Agronomie, eau, énergie','Scénarios et risques','Checkpoint humain','Commande terrain','Impact réel']], [29*mm]*6)]
s += [Spacer(1, 8*mm), P('Principe de gouvernance', 'H1QA'), P('Chaque agent doit retourner une recommandation, les données utilisées, les sources, le niveau de confiance, l impact attendu et le checkpoint humain nécessaire. Les actions critiques restent confirmées par un agriculteur, un ingénieur ou un responsable habilité.', 'BodyQA'), P('État actuel', 'H2QA'), P('Les pages sont déjà organisées autour de ces domaines, mais les données opérationnelles proviennent encore principalement de données de démonstration. La mise en production nécessite les sources et interfaces décrites dans ce document.', 'BodyQA'), PageBreak()]

s += [P('1. Pages, agents et données', 'H1QA'), make_table([
['Page','Agent principal','Données indispensables'],
['Dashboard','Orchestrateur des opérations','Zones, statuts, humidité, irrigation, alertes, énergie, horodatage'],
['Farm / exploitation','Agent exploitation','Ferme, surface, zones, cultures, sols, rendement, récolte'],
['Jumeau numérique / carte','Vision satellite + SIG','GPS, limites, images, NDVI, humidité, altitude, scènes et nuages'],
['Parcelles & zones','Agronomie parcellaire','Culture, variété, plantation, sol, capteurs, historique, rendement'],
['Devices & connexions','IoT / communication','Appareil, firmware, signal, ping, MQTT, fréquence, payload, connexions'],
['Irrigation','Décision eau','Humidité, seuil, météo, débit, pression, réservoir, énergie, vannes'],
['Énergie & solaire','Optimisation énergie','Production PV, pompe, batterie, STEG, météo, coût kWh'],
['Analytics','Analytique impact','Eau, énergie, rendement, coûts, prévision, réel, comparaisons'],
['Intelligence','Coordination humaine','Problèmes, preuves, checkpoints, ingénieur, résolution, impact'],
['Prévisions','Marché agricole','Offre, demande, prix, saison, gouvernorat, météo, confiance'],
['Planning','Planification culturale','Cultures, eau, énergie, sol, rendement, prix, risques, calendrier'],
['Marketplace','Rentabilité et vente','Coûts, prix, rendement, transport, qualité, marge, disponibilité'],
['Notifications','Surveillance','Événements, seuils, anomalies, criticité, sources, actions'],
['Settings / login','Gouvernance et identité','Utilisateurs, rôles, permissions, consentement, audit, MFA'],
], [36*mm, 42*mm, 96*mm])]
s += [Spacer(1, 7*mm), P('Agents transversaux', 'H2QA'), make_table([['Agent','Responsabilité'], ['Orchestrateur','Coordonne, priorise, bloque les conflits et applique les règles de sécurité.'], ['Agronomie','Interprète croissance, stress, sol, NDVI, rendement et risques.'], ['Eau / irrigation','Calcule le besoin, vérifie débit et pression, propose ou déclenche un cycle autorisé.'], ['Énergie','Choisit la fenêtre de pompage selon soleil, batterie, pompe, réseau et coût.'], ['Vision satellite','Compare les scènes, détecte croissance, stress et anomalies.'], ['Marché / rentabilité','Calcule coûts, prix, marge, scénarios et effets de la consommation.'], ['Humain / ingénieur','Confirme, modifie, refuse et documente les décisions à risque.']], [40*mm, 134*mm]), PageBreak()]

s += [P('2. Données communes obligatoires', 'H1QA'), P('Toutes les données doivent être traçables. Une valeur sans unité, date, source ou zone ne doit pas être utilisée pour une décision automatique.', 'BodyQA'), make_table([['Champ','Utilité','Exemple'], ['id / farmId / zoneId','Identifier la donnée et son périmètre','zone-4 / farm-el-baraka'], ['value + unit','Éviter les ambiguïtés','38.2 / %'], ['timestamp','Comparer dans le temps','2026-11-22T14:15:00Z'], ['source / sourceType','Connaître l origine','ESP32 / sensor'], ['quality','Écarter les données douteuses','good, suspect, missing'], ['confidence','Exprimer l incertitude','0 à 100 %'], ['location','Relier mesure et parcelle','longitude, latitude'], ['correlationId','Relier mesure, décision et action','cycle-zone-b-001']], [38*mm, 72*mm, 64*mm])]
s += [P('Format de décision', 'H2QA'), make_table([['agentId','inputs','sources','checkpoint','recommendation','impact','status'], ['agent-irrigation','humidité + seuil + solaire','ESP32, météo, historique','confirmer zone critique','ouvrir vanne 45 min','eau économisée, rendement protégé','proposed']], [22*mm, 28*mm, 28*mm, 31*mm, 29*mm, 30*mm, 20*mm])]
s += [P('Sources réelles à brancher', 'H1QA'), make_table([['Source','Données','Fréquence','Usage'], ['ESP32 / LoRa','Humidité, température, batterie, signal, ping','1 à 5 min','Irrigation et diagnostic'], ['Débit / pression','Débit, pression, volume total','5 à 10 s pendant cycle','Vérifier action réelle'], ['Pompe / vanne','État, puissance, durée, défaut','Temps réel','Sécurité et journal'], ['Onduleur / batterie','Production, SoC, charge, réseau','5 à 10 s','Décision énergie'], ['Sentinel-2 / Copernicus','Scène, bandes, NDVI, nuages','Nouvelle scène','Croissance et stress'], ['Météo locale','Température, pluie, vent, ET0','15 à 60 min','Prévision eau'], ['Factures / ERP','Intrants, salaires, transport, emballage','Chaque facture','Coût par m² et marge'], ['Marché','Prix, demande, volumes, contrats','Journalier à hebdomadaire','Planification et vente'], ['Ingénieurs / agriculteurs','Observation, validation, cause, résolution','Chaque intervention','Apprentissage supervisé']], [34*mm, 62*mm, 31*mm, 45*mm]), PageBreak()]

s += [P('3. Règles de décision et contrôles', 'H1QA'), make_table([['Niveau','Exemple','Action agent','Validation'], ['Information','Humidité stable au-dessus du seuil','Afficher une tendance','Aucune'], ['Recommandation','Décaler le pompage à la fenêtre solaire','Proposer un scénario avec impact','Agriculteur si coût ou rendement affecté'], ['Action contrôlée','Ouvrir une vanne 45 minutes','Commande limitée et journalisée','Règles de sécurité + autorisation'], ['Critique','Stress hydrique ou capteur contradictoire','Bloquer l automatisation et notifier','Ingénieur obligatoire'], ['Politique / public','Agrégation régionale ou pénurie','Scénarios et incertitude','Validation humaine et traçabilité']], [28*mm, 47*mm, 57*mm, 42*mm])]
s += [P('Journal d audit obligatoire', 'H2QA'), P('Pour chaque décision : agent, utilisateur, données utilisées, sources, version du modèle, règle appliquée, validation, commande envoyée et résultat réel observé.', 'BodyQA'), P('Indicateurs d impact', 'H2QA'), make_table([['Domaine','Mesures avant / après'], ['Eau','Litres par zone, m³ par hectare, économie sans baisse de rendement'], ['Énergie','kWh solaire, kWh réseau, coût de pompage, autonomie'], ['Agronomie','NDVI, humidité, stress, rendement, qualité, pertes'], ['Économie','coût par m², coût/kg, chiffre d affaires, gain net, marge'], ['Coopération','capteurs partagés, surface mutualisée, achats groupés, transport évité'], ['Tunisie','salinité, disponibilité de l eau, météo, gouvernorat, saison, prix locaux']], [35*mm, 139*mm])]
s += [P('Important', 'H2QA'), P('Les capteurs, scènes satellite, prix, connexions entre fermes et impacts affichés dans le prototype doivent être marqués simulated tant qu ils ne proviennent pas d une source vérifiée.', 'BodyQA'), PageBreak()]

s += [P('4. Ordre recommandé de mise en production', 'H1QA'), make_table([['Étape','Livrable','Résultat attendu'], ['01','Base de données et identités','Ferme, zones, appareils, utilisateurs, rôles, permissions.'], ['02','Télémétrie réelle','ESP32, LoRa/MQTT, historique, qualité et horodatage.'], ['03','Irrigation et énergie','Débit, pression, vanne, pompe, solaire, batterie, arrêt urgence.'], ['04','Satellite et météo','Sentinel-2, NDVI, scènes, nuages, météo et historique.'], ['05','Agents spécialisés','Agronomie, eau, énergie, appareils, marché, rentabilité.'], ['06','Humain dans la boucle','Checkpoints, validation, refus, documentation, notifications.'], ['07','Orchestrateur','Coordination, conflits, priorités et règles d action.'], ['08','Coopération et marketplace','Connexions fermes, ressources, achats, ventes et contrats.']], [20*mm, 48*mm, 106*mm])]
s += [Spacer(1, 10*mm), P('Critère de passage en production', 'H2QA'), P('Une fonctionnalité est prête uniquement si ses données sont identifiées, sa qualité contrôlée, ses décisions traçables, ses erreurs visibles, son impact mesuré et un humain peut arrêter ou contester l action.', 'BodyQA'), Spacer(1, 12*mm), P('<b>Conclusion</b><br/>QATRA doit fonctionner comme un système d observation et d apprentissage contrôlé : les agents proposent, les sources justifient, les checkpoints sécurisent, et les résultats réels améliorent les décisions suivantes.', 'BodyQA')]

doc.build(s, onFirstPage=footer, onLaterPages=footer)
print(OUT)
