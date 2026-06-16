# ================================================================
# CEPHALOMETRIC STREAMLIT CLIENT — v5
# Analyses: Ricketts, Steiner, Downs, Tweed, McNamara,
#           Bjork-Jarabak, Wits, Rakosi, Segner-Hasund,
#           Eastman, McNamara, ABO, Quick
# Tracés automatiques par analyse
# Calibration, Zoom, Pan, Export PNG/JSON/PDF
# ================================================================
import base64, json, os
import cv2, numpy as np, requests
import streamlit as st
import pandas as pd

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ─────────────────────────────────────────────────────────────────
# LANDMARK SET (29 prédits + 4 additionnels manuels possibles)
# Ajuster l'ordre 1-29 pour correspondre à votre dataset
# ─────────────────────────────────────────────────────────────────
LM_META = {
    1: {"abbr": "Ar", "name": "Articulare"},
    2: {"abbr": "N", "name": "Nasion"},
    3: {"abbr": "Or", "name": "Orbitale"},
    4: {"abbr": "Po", "name": "Porion"},
    5: {"abbr": "Ba", "name": "Basion"},
    6: {"abbr": "B", "name": "Point B (Supramentale)"},
    7: {"abbr": "Pog", "name": "Pogonion"},
    8: {"abbr": "Me", "name": "Menton"},
    9: {"abbr": "Go", "name": "Gonion"},
    10: {"abbr": "A", "name": "Point A (Subspinale)"},
    11: {"abbr": "PNS", "name": "Épine Nasale Postérieure"},
    12: {"abbr": "Ui", "name": "Incisive Sup. (bord incisif)"},
    13: {"abbr": "S", "name": "Sella"},
    14: {"abbr": "Ua", "name": "Incisive Sup. (apex)"},
    15: {"abbr": "Ii", "name": "Incisive Inf. (bord incisif)"},
    16: {"abbr": "ANS", "name": "Épine Nasale Antérieure"},
    17: {"abbr": "La", "name": "Incisive Inf. (apex)"},
    18: {"abbr": "Occ", "name": "Centre Occlusal"},
    19: {"abbr": "PM", "name": "Protubérance Mentonnière"},
    20: {"abbr": "U6", "name": "Molaire Sup. (mésial)"},
    21: {"abbr": "Pn", "name": "Pronasal (pointe nez)"},
    22: {"abbr": "Ul", "name": "Lèvre Supérieure"},
    23: {"abbr": "Li", "name": "Lèvre Inférieure"},
    24: {"abbr": "Pog'", "name": "Pogonion (tissus mous)"},
    25: {"abbr": "PT", "name": "Point PT (Ptérygoïde)"},
    26: {"abbr": "Xi", "name": "Point Xi"},
    27: {"abbr": "DC", "name": "Point DC"},
    28: {"abbr": "Gn", "name": "Gnathion"},
    29: {"abbr": "CF", "name": "Centre de la Face"},
}

# ─────────────────────────────────────────────────────────────────
# TRACÉS ANATOMIQUES AUTOMATIQUES
# type: "spline"          → courbe Catmull-Rom lisse à travers lms
#       "tooth_ui"        → dessin schématique incisive sup.
#       "tooth_li"        → dessin schématique incisive inf.
#       "tooth_u6"        → dessin schématique molaire sup.
#       "straight"        → polyline droite
# ─────────────────────────────────────────────────────────────────
ANATOMICAL_TRACINGS = [
    # ── Squelette crânio-facial ───────────────────────────────
    {"id":"cranial_base",  "name":"Base crânienne (Ba-S-N)",
     "type":"spline","lms": [10, 11, 5],
     "color":"#4FC3F7","width":1.5,"dash":False},

    {"id":"facial_skeleton","name":"Squelette facial (N→Or→ANS)",
     "type":"spline","lms": [5, 6, 2, 1],
     "color":"#4FC3F7","width":1.5,"dash":False},

    {"id":"palatal_plane",  "name":"Plan palatin (PNS→ANS)",
     "type":"straight","lms": [8, 2],
     "color":"#4FC3F7","width":1.5,"dash":False},

    # ── Mandibule ─────────────────────────────────────────────
    {"id":"mandible_body", "name":"Corps mandibulaire",
     "type":"spline","lms": [12, 15, 4, 7],
     "color":"#4FC3F7","width":1.5,"dash":False},

    {"id":"ramus",          "name":"Ramus (Co→Ar→Go)",
     "type":"spline","lms": [13, 12, 15],
     "color":"#4FC3F7","width":1.5,"dash":False},

    # ── Profil tissus mous ────────────────────────────────────
    {"id":"soft_profile",  "name":"Profil tissus mous",
     "type":"spline","lms": [27, 9, 29, 26, 25, 28],
     "color":"#80DEEA","width":1.5,"dash":False},

    # ── Dents ─────────────────────────────────────────────────
    {"id":"tooth_ui",      "name":"Incisive sup. (schéma)",
     "type":"tooth_ui","lms": [21, 22],
     "color":"#81C784","width":1.5,"dash":False},

    {"id":"tooth_li",      "name":"Incisive inf. (schéma)",
     "type":"tooth_li","lms": [24, 18],
     "color":"#81C784","width":1.5,"dash":False},

    {"id":"tooth_u6",      "name":"Molaire sup. (schéma)",
     "type":"tooth_u6","lms": [20, 23],
     "color":"#81C784","width":1.5,"dash":False},

    {"id":"tooth_l6",      "name":"Molaire inf. (schéma)",
     "type":"tooth_l6","lms": [17, 19],
     "color":"#81C784","width":1.5,"dash":False},
]

# ─────────────────────────────────────────────────────────────────
# DÉFINITIONS DES ANALYSES CÉPHALOMÉTRIQUES
# Chaque analyse : planes (lignes mesure) + measurements (normes)
# ─────────────────────────────────────────────────────────────────
# Format plane: {id, name, lm1, lm2, color, ext(bool)}
# Format meas : {nr, param, fn_key, args(lm ids), norm, sd, unit, age_adj(bool)}
# fn_key references a JS calculation function

ANALYSES_DEF = {

"Ricketts": {
  "color":"#4fc3f7",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",     "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"SN",   "name":"S-N",                "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"BaN",  "name":"Ba-N",               "lm1": 10, "lm2": 5,  "color":"#4FC3F7","ext":True},
    {"id":"Mand", "name":"Plan mandibulaire",  "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"PP",   "name":"Plan palatin",       "lm1": 8, "lm2": 2, "color":"#CE93D8","ext":True},
    {"id":"NPog", "name":"N-Pog (facial)",     "lm1": 5,  "lm2": 7,  "color":"#FF8A65","ext":True},
    {"id":"APog", "name":"A-Pog (dentaire)",   "lm1": 1,  "lm2": 7,  "color":"#A5D6A7","ext":False},
    {"id":"Eline","name":"Ligne E",            "lm1": 9, "lm2": 28, "color":"#F48FB1","ext":False},
    {"id":"NA",   "name":"N-A",                "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"NB",   "name":"N-B",                "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
    {"id":"BaPT", "name":"PT-Gn",              "lm1": 20, "lm2": 14,  "color":"#B39DDB","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"Cranial Deflection (Ba-N:FH)",    "fn":"angFH","a1": 10,"a2": 5,   "norm":27, "sd":3,   "unit":"°"},
    {"nr":2, "param":"Facial Axis (Ba-N:PT-Gn)",        "fn":"angVV","a1": 10,"a2": 5,"b1": 20,"b2": 14,"norm":90,"sd":3.5,"unit":"°"},
    {"nr":3, "param":"Facial Depth (FH:N-Pog)",         "fn":"angFH","a1": 5, "a2": 7,   "norm":87, "sd":3,   "unit":"°"},
    {"nr":4, "param":"Facial Taper (Go-Gn:N-Pog)",      "fn":"angVV","a1": 15,"a2": 14,"b1": 5,"b2": 7,"norm":68,"sd":4,"unit":"°"},
    {"nr":5, "param":"Mandibular Plane (Go-Gn:FH)",     "fn":"angFH","a1": 15,"a2": 4,   "norm":22, "sd":4,   "unit":"°"},
    {"nr":6, "param":"Corpus Length (Xi-PM)",           "fn":"dist", "a1": 19,"a2": 14,  "norm":65, "sd":5,   "unit":"mm"},
    {"nr":7, "param":"Mandibular Arc (DC-Xi-PM)",       "fn":"ang3", "a1": 13,"a2": 19,"a3": 14,"norm":26,"sd":4,"unit":"°"},
    {"nr":8, "param":"Ramus Xi Position (PT-Xi:FH)",    "fn":"angFH","a1": 20,"a2": 19,  "norm":76, "sd":3,   "unit":"°"},
    {"nr":9, "param":"Gonial Angle (Ar-Go-Gn)",         "fn":"ang3", "a1": 12,"a2": 15,"a3": 14,"norm":130,"sd":7,"unit":"°"},
    {"nr":10,"param":"Maxillary Depth (FH:N-A)",        "fn":"angFH","a1": 5, "a2": 1,   "norm":90, "sd":3,   "unit":"°"},
    {"nr":11,"param":"Maxillary Height (N-CF-A)",       "fn":"ang3", "a1": 5,"a2": 20,"a3": 1,"norm":53,"sd":3,"unit":"°"},
    {"nr":12,"param":"Palatal Plane to FH",             "fn":"angFH","a1": 8,"a2": 2,  "norm":1,  "sd":3.5, "unit":"°"},
    {"nr":13,"param":"Convexity of A (A:N-Pog) mm",    "fn":"ptLine","a1": 1,"l1": 5,"l2": 7,"norm":2,"sd":2,"unit":"mm"},
    {"nr":14,"param":"Lower Face Height (ANS-Xi-PM)",   "fn":"ang3", "a1": 2,"a2": 19,"a3": 14,"norm":47,"sd":4,"unit":"°"},
    {"nr":15,"param":"Lower Incisor to A-Pog",         "fn":"ptLine","a1": 24,"l1": 1,"l2": 7,"norm":1,"sd":2,"unit":"mm"},
    {"nr":16,"param":"Interincisal Angle",              "fn":"angVV","a1": 21,"a2": 23,"b1": 22,"b2": 24,"norm":135,"sd":8,"unit":"°"},
    {"nr":17,"param":"Upper Molar to PtV (U6:PtV)",    "fn":"ptLineV","a1": 27,"l1": 20,"norm":22,"sd":3,"unit":"mm"},
    {"nr":18,"param":"Upper Incisor Protrusion (Ui:APog)","fn":"ptLine","a1": 23,"l1": 1,"l2": 7,"norm":3.5,"sd":2.3,"unit":"mm"},
    {"nr":19,"param":"Overjet (Ui:Li horiz.)",          "fn":"overjet","norm":2.5,"sd":2.5,"unit":"mm"},
    {"nr":20,"param":"Overbite (Ui:Li vert.)",          "fn":"overbite","norm":2.5,"sd":2,"unit":"mm"},
    {"nr":21,"param":"Upper Lip to E-Line",             "fn":"ptLine","a1": 26,"l1": 9,"l2": 28,"norm":-4,"sd":2,"unit":"mm"},
    {"nr":22,"param":"Lower Lip to E-Line",             "fn":"ptLine","a1": 25,"l1": 9,"l2": 28,"norm":-2,"sd":2,"unit":"mm"},
  ]
},

"Steiner": {
  "color":"#FFD700",
  "planes":[
    {"id":"SN",   "name":"S-N",               "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NA",   "name":"N-A",               "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"NB",   "name":"N-B",               "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
    {"id":"NPog", "name":"N-Pog",             "lm1": 5,  "lm2": 7,  "color":"#FF8A65","ext":True},
    {"id":"GoGn", "name":"Go-Gn",             "lm1": 15, "lm2": 14,  "color":"#81C784","ext":True},
    {"id":"OcPl", "name":"Plan occlusal",     "lm1": 23, "lm2": 27, "color":"#CE93D8","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"SNA", "fn":"ang3","a1":11,"a2":5,"a3":1,"norm":82,"sd":2,"unit":"°",
     "info":"Angle entre la base crânienne antérieure et le maxillaire. Évalue la position antéro-postérieure du maxillaire.",
     "evalLow":"Rétrognatie maxillaire","evalHigh":"Prognathie maxillaire"},
    {"nr":2, "param":"SNB", "fn":"ang3","a1":11,"a2":5,"a3":3,"norm":80,"sd":2,"unit":"°",
     "info":"Angle entre la base crânienne antérieure et la mandibule. Évalue la position antéro-postérieure de la mandibule.",
     "evalLow":"Rétrognatie mandibulaire","evalHigh":"Prognathie mandibulaire"},
    {"nr":3, "param":"ANB", "fn":"anb","norm":2,"sd":2,"unit":"°",
     "info":"Différence entre SNA et SNB. Évalue la relation sagittale entre le maxillaire et la mandibule.",
     "evalLow":"Classe III squelettique","evalHigh":"Classe II squelettique"},
    {"nr":4, "param":"OP-SNP", "fn":"angVV","a1":23,"a2":27,"b1":11,"b2":5,"norm":14,"sd":2,"unit":"°",
     "info":"Angle du plan occlusal par rapport à la base du crâne. Évalue l'inclinaison du plan d'occlusion.",
     "evalHigh":"Indique un visage long, une croissance verticale ou un cas d'occlusion squelettique ouverte"},
    {"nr":5, "param":"MP(GoGn)-SNP", "fn":"angVV","a1":15,"a2":14,"b1":11,"b2":5,"norm":32,"sd":3,"unit":"°",
     "info":"Angle du plan mandibulaire par rapport à la base du crâne. Évalue l'inclinaison de la mandibule.",
     "evalHigh":"Indique l'inclinaison postérieure de la mandibule ou un schéma squelettique d'occlusion ouverte"},
    {"nr":6, "param":"+1-NA", "fn":"angVV","a1":21,"a2":23,"b1":5,"b2":1,"norm":22,"sd":2,"unit":"°",
     "info":"Angle de l'incisive supérieure par rapport à la ligne NA. Évalue l'inclinaison de l'incisive supérieure.",
     "evalLow":"Incisive supérieure rétrograde (fréquent en classe II div 2)","evalHigh":"Incisive supérieure proclinée"},
    {"nr":7, "param":"+1:NA", "fn":"ptLine","a1":23,"l1":5,"l2":1,"norm":4,"sd":2,"unit":"mm",
     "info":"Distance de l'incisive supérieure à la ligne NA. Évalue la proéminence de l'incisive supérieure.",
     "evalLow":"Incisives supérieures rétrusives","evalHigh":"Incisives supérieures protrusives"},
    {"nr":8, "param":"-1-NB", "fn":"angVV","a1":22,"a2":24,"b1":5,"b2":3,"norm":25,"sd":2,"unit":"°",
     "info":"Angle de l'incisive inférieure par rapport à la ligne NB. Évalue l'inclinaison de l'incisive inférieure.",
     "evalLow":"Incisive inférieure rétrograde (fréquent en classe II div 2 ou classe III)","evalHigh":"Incisive inférieure proclinée"},
    {"nr":9, "param":"-1:NB", "fn":"ptLine","a1":24,"l1":5,"l2":3,"norm":4,"sd":5,"unit":"mm",
     "info":"Distance de l'incisive inférieure à la ligne NB. Évalue la proéminence de l'incisive inférieure.",
     "evalLow":"Incisives inférieures rétrusives","evalHigh":"Incisives inférieures protrusives"},
    {"nr":10,"param":"-1 to +1", "fn":"angVV","a1":21,"a2":23,"b1":22,"b2":24,"norm":131,"sd":8,"unit":"°",
     "info":"Angle entre l'axe des incisives supérieure et inférieure. Évalue la relation interincisive.",
     "evalLow":"Angle incisif fermé (tendance classe II div 1)","evalHigh":"Angle incisif ouvert (tendance classe II div 2)"},
    {"nr":11,"param":"Rapport de Holdaway", "fn":"ptLine","a1":7,"l1":5,"l2":3,"norm":0,"sd":2,"unit":"mm",
     "info":"Distance du pogonion à la ligne NB. Évalue l'épaisseur de la symphyse mentonnière.",
     "evalLow":"Symphyse fine","evalHigh":"Symphyse épaisse"},
  ]
},

"Downs": {
  "color":"#81C784",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",    "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"NPog", "name":"N-Pog (Facial)",    "lm1": 5,  "lm2": 7,  "color":"#FF8A65","ext":True},
    {"id":"APog", "name":"A-Pog",             "lm1": 1,  "lm2": 7,  "color":"#A5D6A7","ext":False},
    {"id":"Mand", "name":"Plan mandibulaire", "lm1": 15, "lm2": 14,  "color":"#81C784","ext":True},
    {"id":"OcPl", "name":"Plan occlusal",     "lm1": 23, "lm2": 27, "color":"#CE93D8","ext":True},
    {"id":"AB",   "name":"Plan A-B",          "lm1": 1,  "lm2": 3,  "color":"#80DEEA","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"FHP-NPog", "fn":"angFH","a1":5,"a2":7,"norm":88,"sd":4,"unit":"°",
     "info":"Angle facial entre FH et N-Pog. Évalue la position antéro-postérieure de la mandibule.",
     "evalLow":"Mandibule en retrait au niveau du menton (type dolichofacial), fréquent en classe II","evalHigh":"Prognathie mandibulaire"},
    {"nr":2, "param":"Convexité", "fn":"ptLine","a1":1,"l1":5,"l2":7,"norm":0,"sd":5,"unit":"mm",
     "info":"Distance du point A à la ligne N-Pog. Évalue la convexité du profil facial.",
     "evalHigh":"Profil convexe","evalLow":"Profil concave"},
    {"nr":3, "param":"Plan A-B", "fn":"angVV","a1":1,"a2":3,"b1":5,"b2":7,"norm":-5,"sd":5,"unit":"°",
     "info":"Angle entre le plan A-B et N-Pog. Évalue la relation squelettique entre maxillaire et mandibule.",
     "evalLow":"Classe III squelettique","evalHigh":"Classe II squelettique"},
    {"nr":4, "param":"FMA (FHP-GoMe)", "fn":"angFH","a1":15,"a2":4,"norm":22,"sd":5,"unit":"°",
     "info":"Angle du plan mandibulaire (Go-Me) par rapport à FH. Évalue la divergence faciale.",
     "evalHigh":"Indique un modèle de croissance verticale et une tendance à l'occlusion ouverte (dolichofacial)"},
    {"nr":5, "param":"Y-axe (FHP)", "fn":"angFH","a1":11,"a2":14,"norm":59,"sd":4,"unit":"°",
     "info":"Angle de l'axe Y (S-Gn) par rapport à FH. Évalue la direction de croissance faciale.",
     "evalHigh":"Fréquent dans les modèles faciaux de classe II, indique une croissance verticale de la mandibule"},
    {"nr":6, "param":"FHP-OP", "fn":"angFH","a1":23,"a2":27,"norm":9,"sd":4,"unit":"°",
     "info":"Angle du plan occlusal par rapport à FH. Évalue l'inclinaison du plan d'occlusion.",
     "evalLow":"Plan occlusal incliné vers l'arrière","evalHigh":"Plan occlusal incliné vers l'avant"},
    {"nr":7, "param":"-1 to +1", "fn":"angVV","a1":21,"a2":23,"b1":22,"b2":24,"norm":131,"sd":8,"unit":"°",
     "info":"Angle interincisif. Évalue la relation entre les incisives supérieure et inférieure.",
     "evalLow":"Angle incisif fermé","evalHigh":"Angle incisif ouvert"},
    {"nr":8, "param":"IMPA (Downs)", "fn":"angFH_custom","a1":22,"a2":24,"b1":15,"b2":4,"norm":0,"sd":5,"unit":"°",
     "info":"Angle de l'incisive inférieure par rapport au plan mandibulaire (Go-Me). Déviation par rapport à la perpendiculaire.",
     "evalLow":"Incisive inférieure rétrograde","evalHigh":"Incisive inférieure proclinée"},
    {"nr":9, "param":"IOPA (Downs)", "fn":"angFH_custom","a1":22,"a2":24,"b1":23,"b2":27,"norm":15,"sd":4,"unit":"°",
     "info":"Angle de l'incisive inférieure par rapport au plan occlusal.",
     "evalLow":"Inclinaison anormale de l'incisive inférieure","evalHigh":"Inclinaison anormale de l'incisive inférieure"},
    {"nr":10,"param":"+1:APog", "fn":"ptLine","a1":23,"l1":1,"l2":7,"norm":5,"sd":3,"unit":"mm",
     "info":"Distance de l'incisive supérieure à la ligne A-Pog. Évalue la proéminence incisive supérieure.",
     "evalLow":"Incisives supérieures rétrusives","evalHigh":"Incisives supérieures protrusives"},
  ]
},

"Jefferson": {
  "color":"#B39DDB",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",    "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"NPerpFH","name":"N ⟂ FH",          "lm1": 5,  "lm2": 5,  "color":"#B39DDB","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"Jefferson (ANS)", "fn":"perpFH","a1":2,"ref":5,"norm":0,"sd":2,"unit":"mm",
     "info":"Distance horizontale de l'Épine Nasale Antérieure à la verticale passant par Nasion (perpendiculaire à FH).",
     "evalLow":"Classe IIb","evalHigh":"Classe III/Prognathie maxillaire"},
    {"nr":2, "param":"Jefferson (Pog)", "fn":"perpFH","a1":7,"ref":5,"norm":0,"sd":2,"unit":"mm",
     "info":"Distance horizontale du Pogonion à la verticale passant par Nasion (perpendiculaire à FH).",
     "evalLow":"Classe IIb","evalHigh":"Classe III/Prognathie mandibulaire"},
    {"nr":3, "param":"Me:Jeff. vert.", "fn":"ptLine","a1":4,"l1":6,"l2":16,"norm":0,"sd":2,"unit":"mm",
     "info":"Distance verticale du Menton au plan FH. Évalue la position verticale de la mandibule.",
     "evalLow":"Mandibule au-dessus de l'arc vertical de Jefferson. Suggère un modèle de croissance horizontale.","evalHigh":"Mandibule en dessous de l'arc vertical de Jefferson. Suggère un modèle de croissance verticale."},
  ]
},

"Tweed": {
  "color":"#FF8A65",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",    "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"Mand", "name":"Plan mandibulaire", "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"LiAx", "name":"Axe inc. inf.",     "lm1": 22, "lm2": 24, "color":"#CE93D8","ext":True},
  ],
  "measurements":[
    {"nr":1,"param":"FMA (FH:Plan mand.)",     "fn":"angFH","a1": 15,"a2": 4,"norm":25,"sd":5,"unit":"°"},
    {"nr":2,"param":"FMIA (FH:Axe Li)",        "fn":"angFH","a1": 22,"a2": 24,"norm":65,"sd":8,"unit":"°"},
    {"nr":3,"param":"IMPA (Plan mand.:Li)",    "fn":"angVV","a1": 15,"a2": 4,"b1": 22,"b2": 24,"norm":90,"sd":5,"unit":"°"},
    {"nr":4,"param":"Tweed Triangle Sum",      "fn":"triSum","norm":180,"sd":0,"unit":"°"},
  ]
},

"McNamara": {
  "color":"#CE93D8",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",    "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"NperF","name":"N perp. à FH",      "lm1": 5,  "lm2": 5,  "color":"#FFD700","ext":True},  # perpendicular
    {"id":"NA",   "name":"N-A",               "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"Mand", "name":"Plan mandibulaire", "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"Maxillary position (A:perp FH à N)","fn":"perpFH","a1": 1,"ref": 5,"norm":0,"sd":2,"unit":"mm"},
    {"nr":2, "param":"Mandibular position (Pog:perp FH à N)","fn":"perpFH","a1": 7,"ref": 5,"norm":-4,"sd":3,"unit":"mm"},
    {"nr":3, "param":"Effective maxillary length (Co-A)","fn":"dist","a1": None,"a2": 1,"norm":88,"sd":4,"unit":"mm"},
    {"nr":4, "param":"Effective mandib. length (Co-Gn)","fn":"dist","a1": None,"a2": 14,"norm":120,"sd":5,"unit":"mm"},
    {"nr":5, "param":"Ratio Co-A / Co-Gn",            "fn":"ratio","a1": None,"a2": 1,"b1": None,"b2": 14,"norm":0.73,"sd":0.02,"unit":""},
    {"nr":6, "param":"Lower face height (ANS-Me)",     "fn":"dist","a1": 2,"a2": 4,"norm":66,"sd":4,"unit":"mm"},
    {"nr":7, "param":"Facial height ratio (N-Me/S-Go)","fn":"faceRatio","norm":0.69,"sd":0.02,"unit":""},
    {"nr":8, "param":"Mand. Plane to FH",             "fn":"angFH","a1": 15,"a2": 4,"norm":22,"sd":4,"unit":"°"},
    {"nr":9, "param":"Ui to N-A (mm)",                "fn":"ptLine","a1": 23,"l1": 5,"l2": 1,"norm":4,"sd":2,"unit":"mm"},
    {"nr":10,"param":"Li to N-B (mm)",                "fn":"ptLine","a1": 24,"l1": 5,"l2": 3,"norm":4,"sd":2,"unit":"mm"},
  ]
},

"Bjork-Jarabak": {
  "color":"#80DEEA",
  "planes":[
    {"id":"SN",   "name":"S-N",               "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"SAr",  "name":"S-Ar",              "lm1": 11,  "lm2": 12, "color":"#4FC3F7","ext":False},
    {"id":"ArGo", "name":"Ar-Go",             "lm1": 12, "lm2": 15, "color":"#81C784","ext":False},
    {"id":"GoMe", "name":"Go-Me",             "lm1": 15, "lm2": 4,  "color":"#A5D6A7","ext":False},
    {"id":"NGo",  "name":"N-Go",              "lm1": 5,  "lm2": 15, "color":"#FFCC80","ext":False},
    {"id":"SGo",  "name":"S-Go",              "lm1": 11,  "lm2": 15, "color":"#FF8A65","ext":False},
    {"id":"NMe",  "name":"N-Me",              "lm1": 5,  "lm2": 4,  "color":"#FF6B6B","ext":False},
  ],
  "measurements":[
    {"nr":1, "param":"Saddle Angle (N-S-Ar)",       "fn":"ang3","a1": 5,"a2": 11,"a3": 12,"norm":123,"sd":5,"unit":"°"},
    {"nr":2, "param":"Articular Angle (S-Ar-Go)",   "fn":"ang3","a1": 11,"a2": 12,"a3": 15,"norm":143,"sd":6,"unit":"°"},
    {"nr":3, "param":"Gonial Angle total (Ar-Go-Me)","fn":"ang3","a1": 12,"a2": 15,"a3": 4,"norm":130,"sd":7,"unit":"°"},
    {"nr":4, "param":"Upper Gonial (Ar-Go-N)",      "fn":"ang3","a1": 12,"a2": 15,"a3": 5,"norm":52,"sd":4,"unit":"°"},
    {"nr":5, "param":"Lower Gonial (N-Go-Me)",      "fn":"ang3","a1": 5,"a2": 15,"a3": 4,"norm":70,"sd":4,"unit":"°"},
    {"nr":6, "param":"Sum 3 posterior angles",      "fn":"sum3ang","norm":396,"sd":6,"unit":"°"},
    {"nr":7, "param":"Ant. Cranial Base (S-N)",     "fn":"dist","a1": 11,"a2": 5,"norm":71,"sd":3,"unit":"mm"},
    {"nr":8, "param":"Post. Cranial Base (S-Ar)",   "fn":"dist","a1": 11,"a2": 12,"norm":32,"sd":3,"unit":"mm"},
    {"nr":9, "param":"Ramus height (Ar-Go)",        "fn":"dist","a1": 12,"a2": 15,"norm":44,"sd":5,"unit":"mm"},
    {"nr":10,"param":"Mandib. body (Go-Me)",        "fn":"dist","a1": 15,"a2": 4,"norm":71,"sd":5,"unit":"mm"},
    {"nr":11,"param":"Ant. face height (N-Me)",     "fn":"dist","a1": 5,"a2": 4,"norm":119,"sd":6,"unit":"mm"},
    {"nr":12,"param":"Post. face height (S-Go)",    "fn":"dist","a1": 11,"a2": 15,"norm":79,"sd":5,"unit":"mm"},
    {"nr":13,"param":"PFH/AFH ratio × 100",         "fn":"ratio","a1": 11,"a2": 15,"b1": 5,"b2": 4,"norm":63,"sd":3,"unit":"%"},
    {"nr":14,"param":"Facial type (PFH/AFH)",       "fn":"ratio","a1": 11,"a2": 15,"b1": 5,"b2": 4,"norm":0.63,"sd":0.03,"unit":""},
  ]
},

"Wits": {
  "color":"#FFCC80",
  "planes":[
    {"id":"OcPl", "name":"Plan occlusal",     "lm1": 23, "lm2": 27, "color":"#CE93D8","ext":True},
    {"id":"NA",   "name":"N-A",               "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"NB",   "name":"N-B",               "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
  ],
  "measurements":[
    {"nr":1,"param":"Wits AO-BO (plan occlusal)","fn":"wits","norm":0,"sd":2,"unit":"mm"},
    {"nr":2,"param":"SNA",                       "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":82,"sd":2,"unit":"°"},
    {"nr":3,"param":"SNB",                       "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":80,"sd":2,"unit":"°"},
    {"nr":4,"param":"ANB",                       "fn":"anb","norm":2,"sd":2,"unit":"°"},
  ]
},

"Segner-Hasund": {
  "color":"#F48FB1",
  "planes":[
    {"id":"SN",   "name":"NSL (S-N)",          "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NL",   "name":"NL (Plan nasal)",    "lm1": 8, "lm2": 2, "color":"#CE93D8","ext":True},
    {"id":"ML",   "name":"ML (Plan mand.)",    "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"Ba",   "name":"Ba-N",               "lm1": 10, "lm2": 5,  "color":"#4FC3F7","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"SNA",                    "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":82,"sd":3.5,"unit":"°"},
    {"nr":2, "param":"SNB",                    "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":80,"sd":3.5,"unit":"°"},
    {"nr":3, "param":"ANB",                    "fn":"anb","norm":2,"sd":2,"unit":"°"},
    {"nr":4, "param":"NSBa (base crânienne)",  "fn":"ang3","a1": 5,"a2": 11,"a3": 10,"norm":131,"sd":5,"unit":"°"},
    {"nr":5, "param":"NL-NSL (Maxilla:SN)",    "fn":"angVV","a1": 8,"a2": 2,"b1": 11,"b2": 5,"norm":8,"sd":3,"unit":"°"},
    {"nr":6, "param":"ML-NSL (Mand.:SN)",      "fn":"angVV","a1": 15,"a2": 4,"b1": 11,"b2": 5,"norm":32,"sd":5,"unit":"°"},
    {"nr":7, "param":"NL-ML (MMPA)",           "fn":"angVV","a1": 8,"a2": 2,"b1": 15,"b2": 4,"norm":24,"sd":5,"unit":"°"},
    {"nr":8, "param":"NSGn (Y-Axis:SN)",       "fn":"angFH_custom","a1": 11,"a2": 14,"b1": 11,"b2": 5,"norm":66,"sd":3,"unit":"°"},
    {"nr":9, "param":"Ui:NL (inc. sup.:PP)",   "fn":"angVV","a1": 21,"a2": 23,"b1": 8,"b2": 2,"norm":110,"sd":6,"unit":"°"},
    {"nr":10,"param":"Li:ML (inc. inf.:MP)",   "fn":"angVV","a1": 22,"a2": 24,"b1": 15,"b2": 4,"norm":94,"sd":6,"unit":"°"},
    {"nr":11,"param":"Interincisal Angle",     "fn":"angVV","a1": 21,"a2": 23,"b1": 22,"b2": 24,"norm":132,"sd":8,"unit":"°"},
  ]
},

"Rakosi": {
  "color":"#A5D6A7",
  "planes":[
    {"id":"SN",   "name":"S-N",               "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NL",   "name":"Plan nasal",        "lm1": 8, "lm2": 2, "color":"#CE93D8","ext":True},
    {"id":"ML",   "name":"Plan mand.",        "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"ArGo", "name":"Ar-Go",             "lm1": 12, "lm2": 15, "color":"#4FC3F7","ext":False},
    {"id":"GoGn", "name":"Go-Gn",             "lm1": 15, "lm2": 14,  "color":"#A5D6A7","ext":False},
  ],
  "measurements":[
    {"nr":1, "param":"SNA",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":82,"sd":2,"unit":"°"},
    {"nr":2, "param":"SNB",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":80,"sd":2,"unit":"°"},
    {"nr":3, "param":"ANB",                   "fn":"anb","norm":2,"sd":2,"unit":"°"},
    {"nr":4, "param":"GoGn to SN",            "fn":"angVV","a1": 15,"a2": 14,"b1": 11,"b2": 5,"norm":32,"sd":5,"unit":"°"},
    {"nr":5, "param":"NL to SN",              "fn":"angVV","a1": 8,"a2": 2,"b1": 11,"b2": 5,"norm":7,"sd":3,"unit":"°"},
    {"nr":6, "param":"NL to ML (MMPA)",       "fn":"angVV","a1": 8,"a2": 2,"b1": 15,"b2": 4,"norm":25,"sd":5,"unit":"°"},
    {"nr":7, "param":"Gonial angle (Ar-Go-Gn)","fn":"ang3","a1": 12,"a2": 15,"a3": 14,"norm":128,"sd":7,"unit":"°"},
    {"nr":8, "param":"Ramus Inclination",     "fn":"angFH","a1": 12,"a2": 15,"norm":76,"sd":4,"unit":"°"},
    {"nr":9, "param":"S-Ar distance",         "fn":"dist","a1": 11,"a2": 12,"norm":32,"sd":3,"unit":"mm"},
    {"nr":10,"param":"Ar-Go distance",        "fn":"dist","a1": 12,"a2": 15,"norm":44,"sd":4,"unit":"mm"},
    {"nr":11,"param":"Go-Gn distance",        "fn":"dist","a1": 15,"a2": 14,"norm":71,"sd":5,"unit":"mm"},
    {"nr":12,"param":"Ui to NL (angle)",      "fn":"angVV","a1": 21,"a2": 23,"b1": 8,"b2": 2,"norm":110,"sd":6,"unit":"°"},
    {"nr":13,"param":"Li to ML (IMPA)",       "fn":"angVV","a1": 22,"a2": 24,"b1": 15,"b2": 4,"norm":94,"sd":7,"unit":"°"},
    {"nr":14,"param":"Interincisal Angle",    "fn":"angVV","a1": 21,"a2": 23,"b1": 22,"b2": 24,"norm":130,"sd":8,"unit":"°"},
  ]
},

"Eastman": {
  "color":"#FFAB91",
  "planes":[
    {"id":"SN",   "name":"S-N",               "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NL",   "name":"Plan nasal (NL)",   "lm1": 8, "lm2": 2, "color":"#CE93D8","ext":True},
    {"id":"ML",   "name":"Plan mand. (ML)",   "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"NA",   "name":"N-A",               "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"NB",   "name":"N-B",               "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"SNA",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":81,"sd":3,"unit":"°"},
    {"nr":2, "param":"SNB",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":78,"sd":3,"unit":"°"},
    {"nr":3, "param":"ANB (Eastman corr.)",   "fn":"anb","norm":3,"sd":2,"unit":"°"},
    {"nr":4, "param":"MMPA (NL-ML)",          "fn":"angVV","a1": 8,"a2": 2,"b1": 15,"b2": 4,"norm":27,"sd":5,"unit":"°"},
    {"nr":5, "param":"Ui to MaxPlane (NL)",   "fn":"angVV","a1": 21,"a2": 23,"b1": 8,"b2": 2,"norm":109,"sd":6,"unit":"°"},
    {"nr":6, "param":"Li to MandPlane (ML)",  "fn":"angVV","a1": 22,"a2": 24,"b1": 15,"b2": 4,"norm":93,"sd":6,"unit":"°"},
    {"nr":7, "param":"Interincisal Angle",    "fn":"angVV","a1": 21,"a2": 23,"b1": 22,"b2": 24,"norm":133,"sd":8,"unit":"°"},
    {"nr":8, "param":"Ui to NA (mm)",         "fn":"ptLine","a1": 23,"l1": 5,"l2": 1,"norm":4,"sd":2,"unit":"mm"},
    {"nr":9, "param":"Li to NB (mm)",         "fn":"ptLine","a1": 24,"l1": 5,"l2": 3,"norm":4,"sd":2,"unit":"mm"},
    {"nr":10,"param":"Z-Angle (FH:Ul-Pog')",  "fn":"angFH","a1": 26,"a2": 28,"norm":75,"sd":5,"unit":"°"},
  ]
},

"ABO": {
  "color":"#B39DDB",
  "planes":[
    {"id":"FH",   "name":"FH (Francfort)",    "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"SN",   "name":"S-N",               "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NA",   "name":"N-A",               "lm1": 5,  "lm2": 1,  "color":"#80DEEA","ext":True},
    {"id":"NB",   "name":"N-B",               "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
    {"id":"Mand", "name":"Plan mand.",        "lm1": 15, "lm2": 4,  "color":"#81C784","ext":True},
    {"id":"OcPl", "name":"Plan occlusal",     "lm1": 23, "lm2": 27, "color":"#CE93D8","ext":True},
  ],
  "measurements":[
    {"nr":1, "param":"SNA",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":82,"sd":2,"unit":"°"},
    {"nr":2, "param":"SNB",                   "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":80,"sd":2,"unit":"°"},
    {"nr":3, "param":"ANB",                   "fn":"anb","norm":2,"sd":2,"unit":"°"},
    {"nr":4, "param":"FMA (FH:GoMe)",         "fn":"angFH","a1": 15,"a2": 4,"norm":25,"sd":5,"unit":"°"},
    {"nr":5, "param":"IMPA (GoMe:Li)",        "fn":"angVV","a1": 15,"a2": 4,"b1": 22,"b2": 24,"norm":95,"sd":5,"unit":"°"},
    {"nr":6, "param":"FMIA (FH:Li)",          "fn":"angFH","a1": 22,"a2": 24,"norm":65,"sd":7,"unit":"°"},
    {"nr":7, "param":"GoGn to SN",            "fn":"angVV","a1": 15,"a2": 14,"b1": 11,"b2": 5,"norm":32,"sd":5,"unit":"°"},
    {"nr":8, "param":"Occlusal plane to SN",  "fn":"angVV","a1": 23,"a2": 27,"b1": 11,"b2": 5,"norm":14,"sd":4,"unit":"°"},
    {"nr":9, "param":"Ui to NA (mm)",         "fn":"ptLine","a1": 23,"l1": 5,"l2": 1,"norm":4,"sd":2,"unit":"mm"},
    {"nr":10,"param":"Li to NB (mm)",         "fn":"ptLine","a1": 24,"l1": 5,"l2": 3,"norm":4,"sd":2,"unit":"mm"},
    {"nr":11,"param":"Ui to NA (angle)",      "fn":"angVV","a1": 21,"a2": 23,"b1": 5,"b2": 1,"norm":22,"sd":5,"unit":"°"},
    {"nr":12,"param":"Interincisal Angle",    "fn":"angVV","a1": 21,"a2": 23,"b1": 22,"b2": 24,"norm":130,"sd":6,"unit":"°"},
    {"nr":13,"param":"Overjet",               "fn":"overjet","norm":2,"sd":1,"unit":"mm"},
    {"nr":14,"param":"Overbite",              "fn":"overbite","norm":2,"sd":1,"unit":"mm"},
  ]
},

"Quick": {
  "color":"#E0E0E0",
  "planes":[
    {"id":"FH",   "name":"FH",               "lm1": 6,  "lm2": 16,  "color":"#FF6B6B","ext":True},
    {"id":"SN",   "name":"S-N",              "lm1": 11,  "lm2": 5,  "color":"#FFD700","ext":True},
    {"id":"NB",   "name":"N-B",             "lm1": 5,  "lm2": 3,  "color":"#FFCC80","ext":True},
  ],
  "measurements":[
    {"nr":1,"param":"SNA",     "fn":"ang3","a1": 11,"a2": 5,"a3": 1,"norm":82,"sd":2,"unit":"°"},
    {"nr":2,"param":"SNB",     "fn":"ang3","a1": 11,"a2": 5,"a3": 3,"norm":80,"sd":2,"unit":"°"},
    {"nr":3,"param":"ANB",     "fn":"anb","norm":2,"sd":2,"unit":"°"},
    {"nr":4,"param":"FMA",     "fn":"angFH","a1": 15,"a2": 4,"norm":25,"sd":5,"unit":"°"},
    {"nr":5,"param":"IMPA",    "fn":"angVV","a1": 15,"a2": 4,"b1": 22,"b2": 24,"norm":95,"sd":5,"unit":"°"},
    {"nr":6,"param":"Overjet", "fn":"overjet","norm":2,"sd":1,"unit":"mm"},
    {"nr":7,"param":"Overbite","fn":"overbite","norm":2,"sd":1,"unit":"mm"},
  ]
},

}  # end ANALYSES_DEF


# ─────────────────────────────────────────────────────────────────
# JS CANVAS ENGINE (template — placeholders replaced at runtime)
# ─────────────────────────────────────────────────────────────────
JS_ENGINE = r"""
// ══════════════════════════════════════════════════════════
//  INJECTED DATA
// ══════════════════════════════════════════════════════════
__INJECTED_DATA__

// ══════════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════════
let lms      = JSON.parse(JSON.stringify(INIT_LMS));
let view     = {tx:0,ty:0,sc:1};
let mode     = 'sel';   // sel|trc|pln|era
let lblMode  = INIT_LBL_MODE;
let drag     = null;
let isPan    = false;
let panStart = null, viewStart = null;
let customTraces  = [];
let currentTrace  = null;
let customPlanes  = [];
let drawingPlane  = null;
let calibState    = null, calibPt1 = null;
let pixelSpacing  = INIT_PS;
let activeAnalysis= 'Ricketts';
let colorIdx      = 0;
const TC = ['#4fc3f7','#81c784','#ffb74d','#f48fb1','#ce93d8','#80cbc4','#fff176','#ff8a65'];

// tracing visibility
let tracingVis = {};
ANATOMICAL.forEach(t => { tracingVis[t.id] = false; });

// plane visibility per analysis
let planeVis = {};
ANALYSES && Object.keys(ANALYSES).forEach(k => { ANALYSES[k].planes.forEach(p => { planeVis[p.id] = false; }); });

// ══════════════════════════════════════════════════════════
//  CANVAS SETUP
// ══════════════════════════════════════════════════════════
const wrap   = document.getElementById('cv');
const canvas = document.getElementById('mc');
const ctx    = canvas.getContext('2d');
const tip    = document.getElementById('tip');
const stEl   = document.getElementById('st');
let img = new Image();
img.onload = () => { loadToothSVGs(); resize(); fitView(); buildSidePanel(); R(); };
img.src = 'data:image/png;base64,' + IMG_B64;

new ResizeObserver(()=>{ resize(); R(); }).observe(wrap);
function resize(){ canvas.width=wrap.clientWidth; canvas.height=wrap.clientHeight; }

function fitView(){
  if(!img.naturalWidth) return;
  const s=Math.min(wrap.clientWidth/img.naturalWidth, wrap.clientHeight/img.naturalHeight)*0.96;
  view={tx:(wrap.clientWidth-img.naturalWidth*s)/2, ty:(wrap.clientHeight-img.naturalHeight*s)/2, sc:s};
  R();
}
function zoom(f,cx,cy){
  cx=cx||wrap.clientWidth/2; cy=cy||wrap.clientHeight/2;
  view.tx=cx-(cx-view.tx)*f; view.ty=cy-(cy-view.ty)*f; view.sc*=f; R();
}

// ══════════════════════════════════════════════════════════
//  SVG TOOTH DRAWING
// ══════════════════════════════════════════════════════════
const TOOTH_SVG={
  svgUi:{url:'/static/svg/superiorIncisor.svg',vb:{w:35.18,h:64.26}},
  svgLi:{url:'/static/svg/inferiorIncisor.svg', vb:{w:44.48,h:81.22}},
  svgU6:{url:'/static/svg/superiorMolar.svg',   vb:{w:34.21,h:53.79}},
  svgL6:{url:'/static/svg/inferiorMolar.svg',   vb:{w:41.14,h:56.50}},
};
let svgImgs={};
let svgLoaded=false;
function loadToothSVGs(){
  const c='#81C784'; let n=0,total=0;
  Object.entries(TOOTH_SVG).forEach(([k,cfg])=>{
    total++;
    fetch(cfg.url).then(r=>r.text()).then(svgText=>{
      svgText=svgText.replace(/stroke:#[0-9a-fA-F]+/g,`stroke:${c}`);
      svgText=svgText.replace(/stroke="#[0-9a-fA-F]+"/g,`stroke="${c}"`);
      const blob=new Blob([svgText],{type:'image/svg+xml'});
      const img=new Image();
      img.onload=()=>{svgImgs[k]=img;n++;if(n===total){svgLoaded=true;R();}};
      img.src=URL.createObjectURL(blob);
    });
  });
}


// ══════════════════════════════════════════════════════════
//  RENDERING
// ══════════════════════════════════════════════════════════
function R(){
  if(!img.naturalWidth) return;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.save();
  ctx.translate(view.tx,view.ty); ctx.scale(view.sc,view.sc);

  // Image
  const br=document.getElementById('rng-br').value;
  const ct=document.getElementById('rng-ct').value;
  ctx.filter=`brightness(${br}%) contrast(${ct}%)`; ctx.drawImage(img,0,0); ctx.filter='none';

  // Anatomical tracings
  drawAnatomical();

  // Analysis planes
  const anal = ANALYSES[activeAnalysis];
  if(anal){
    anal.planes.forEach(pl=>{
      if(planeVis[pl.id]===false) return;
      const p1=getLM(pl.lm1), p2=getLM(pl.lm2); if(!p1||!p2) return;
      drawPlane(p1,p2,pl.color,pl.ext,pl.name);
    });
  }

  // Custom planes
  customPlanes.forEach(pl=>{
    ctx.beginPath();ctx.moveTo(pl.x1,pl.y1);ctx.lineTo(pl.x2,pl.y2);
    ctx.strokeStyle=pl.color;ctx.lineWidth=1.5/view.sc;ctx.stroke();
  });
  if(drawingPlane){
    ctx.beginPath();ctx.moveTo(drawingPlane.x1,drawingPlane.y1);ctx.lineTo(drawingPlane.x2,drawingPlane.y2);
    ctx.setLineDash([5/view.sc,4/view.sc]);ctx.strokeStyle='#ffff00';ctx.lineWidth=1.5/view.sc;ctx.stroke();ctx.setLineDash([]);
  }

  // Custom traces
  customTraces.forEach(tr=>{
    if(tr.pts.length<2) return;
    ctx.beginPath();ctx.moveTo(tr.pts[0].x,tr.pts[0].y);
    tr.pts.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));
    ctx.strokeStyle=tr.color;ctx.lineWidth=1.5/view.sc;ctx.stroke();
  });
  if(currentTrace&&currentTrace.pts.length>=2){
    ctx.beginPath();ctx.moveTo(currentTrace.pts[0].x,currentTrace.pts[0].y);
    currentTrace.pts.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));
    ctx.setLineDash([5/view.sc,4/view.sc]);
    ctx.strokeStyle=TC[colorIdx%TC.length];ctx.lineWidth=1.5/view.sc;ctx.stroke();ctx.setLineDash([]);
  }

  // Calibration
  if(calibPt1){ ctx.beginPath();ctx.arc(calibPt1.x,calibPt1.y,6/view.sc,0,2*Math.PI);ctx.fillStyle='#ffff00';ctx.fill(); }

  // Landmarks
  drawLandmarks();
  ctx.restore();
}


// ══════════════════════════════════════════════════════════
//  CATMULL-ROM SPLINE  +  TOOTH DRAWINGS
// ══════════════════════════════════════════════════════════

/** Draw a smooth Catmull-Rom spline through screen-space pts array [{x,y}] */
function splineThrough(pts, tension=0.5){
  if(pts.length<2) return;
  // Extend phantom points at both ends
  const ext=[pts[0], ...pts, pts[pts.length-1]];
  ctx.moveTo(pts[0].x, pts[0].y);
  for(let i=0; i<pts.length-1; i++){
    const p0=ext[i], p1=ext[i+1], p2=ext[i+2], p3=ext[i+3]||ext[ext.length-1];
    const cp1x=p1.x+(p2.x-p0.x)*tension/3;
    const cp1y=p1.y+(p2.y-p0.y)*tension/3;
    const cp2x=p2.x-(p3.x-p1.x)*tension/3;
    const cp2y=p2.y-(p3.y-p1.y)*tension/3;
    ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2.x,p2.y);
  }
}

function drawUpperIncisor(apex, tip, color, lw){
  const img=svgImgs.svgUi; if(!img||!img.naturalWidth)return;
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const vb=TOOTH_SVG.svgUi.vb,scale=len/vb.h,sw=vb.w*scale,sh=vb.h*scale;
  ctx.save();ctx.translate(apex.x,apex.y);ctx.rotate(Math.atan2(dx,dy));
  ctx.drawImage(img,-sw/2,0,sw,sh);ctx.restore();
}
function drawLowerIncisor(apex, tip, color, lw){
  const img=svgImgs.svgLi; if(!img||!img.naturalWidth)return;
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const vb=TOOTH_SVG.svgLi.vb,scale=len/vb.h,sw=vb.w*scale,sh=vb.h*scale;
  ctx.save();ctx.translate(apex.x,apex.y);ctx.rotate(Math.atan2(dx,dy));
  ctx.drawImage(img,-sw/2,0,sw,sh);ctx.restore();
}
function drawUpperMolar(lm1,lm2,color,lw){
  const img=svgImgs.svgU6; if(!img||!img.naturalWidth)return;
  const cx=(lm1.x+lm2.x)/2,cy=(lm1.y+lm2.y)/2;
  const ui=getLM(22),ua=getLM(21);
  const unit=(ui&&ua)?Math.hypot(ui.x-ua.x,ui.y-ua.y)*0.22:14/view.sc;
  const vb=TOOTH_SVG.svgU6.vb,scale=unit*2.0/vb.w,halfH=scale*vb.h/2;
  const apex={x:cx,y:cy-halfH},tip={x:cx,y:cy+halfH};
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const sw=vb.w*scale,sh=vb.h*scale;
  ctx.save();ctx.translate(apex.x,apex.y);ctx.rotate(Math.atan2(dx,dy));
  ctx.drawImage(img,-sw/2,0,sw,sh);ctx.restore();
}
function drawLowerMolar(lm1,lm2,color,lw){
  const img=svgImgs.svgL6; if(!img||!img.naturalWidth)return;
  const cx=(lm1.x+lm2.x)/2,cy=(lm1.y+lm2.y)/2;
  const li=getLM(18),la=getLM(24);
  const unit=(li&&la)?Math.hypot(li.x-la.x,li.y-la.y)*0.22:14/view.sc;
  const vb=TOOTH_SVG.svgL6.vb,scale=unit*2.0/vb.w,halfH=scale*vb.h/2;
  const apex={x:cx,y:cy+halfH},tip={x:cx,y:cy-halfH};
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const sw=vb.w*scale,sh=vb.h*scale;
  ctx.save();ctx.translate(apex.x,apex.y);ctx.rotate(Math.atan2(dx,dy));
  ctx.drawImage(img,-sw/2,0,sw,sh);ctx.restore();
}
function drawUpperIncisorOnCtx(x,apex,tip){
  const img=svgImgs.svgUi; if(!img||!img.naturalWidth)return;
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const vb=TOOTH_SVG.svgUi.vb,scale=len/vb.h,sw=vb.w*scale,sh=vb.h*scale;
  x.save();x.translate(apex.x,apex.y);x.rotate(Math.atan2(dx,dy));
  x.drawImage(img,-sw/2,0,sw,sh);x.restore();
}
function drawLowerIncisorOnCtx(x,apex,tip){
  const img=svgImgs.svgLi; if(!img||!img.naturalWidth)return;
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const vb=TOOTH_SVG.svgLi.vb,scale=len/vb.h,sw=vb.w*scale,sh=vb.h*scale;
  x.save();x.translate(apex.x,apex.y);x.rotate(Math.atan2(dx,dy));
  x.drawImage(img,-sw/2,0,sw,sh);x.restore();
}
function drawUpperMolarOnCtx(x,lm1,lm2){
  const img=svgImgs.svgU6; if(!img||!img.naturalWidth)return;
  const cx=(lm1.x+lm2.x)/2,cy=(lm1.y+lm2.y)/2;
  const ui=getLM(22),ua=getLM(21);
  const unit=(ui&&ua)?Math.hypot(ui.x-ua.x,ui.y-ua.y)*0.22:14/view.sc;
  const vb=TOOTH_SVG.svgU6.vb,scale=unit*2.0/vb.w,halfH=scale*vb.h/2;
  const apex={x:cx,y:cy-halfH},tip={x:cx,y:cy+halfH};
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const sw=vb.w*scale,sh=vb.h*scale;
  x.save();x.translate(apex.x,apex.y);x.rotate(Math.atan2(dx,dy));
  x.drawImage(img,-sw/2,0,sw,sh);x.restore();
}
function drawLowerMolarOnCtx(x,lm1,lm2){
  const img=svgImgs.svgL6; if(!img||!img.naturalWidth)return;
  const cx=(lm1.x+lm2.x)/2,cy=(lm1.y+lm2.y)/2;
  const li=getLM(18),la=getLM(24);
  const unit=(li&&la)?Math.hypot(li.x-la.x,li.y-la.y)*0.22:14/view.sc;
  const vb=TOOTH_SVG.svgL6.vb,scale=unit*2.0/vb.w,halfH=scale*vb.h/2;
  const apex={x:cx,y:cy+halfH},tip={x:cx,y:cy-halfH};
  const dx=tip.x-apex.x,dy=tip.y-apex.y,len=Math.hypot(dx,dy); if(len<4)return;
  const sw=vb.w*scale,sh=vb.h*scale;
  x.save();x.translate(apex.x,apex.y);x.rotate(Math.atan2(dx,dy));
  x.drawImage(img,-sw/2,0,sw,sh);x.restore();
}

/** Dispatch all anatomical tracings */
function drawAnatomical(){
  ANATOMICAL.forEach(t=>{
    if(!tracingVis[t.id]) return;
    const pts=t.lms.map(id=>getLM(id)).filter(Boolean);

    ctx.strokeStyle=t.color;
    ctx.lineWidth=t.width/view.sc;
    if(t.dash) ctx.setLineDash([6/view.sc,4/view.sc]);

    if(t.type==='spline'){
      if(pts.length<2){ctx.setLineDash([]);return;}
      ctx.beginPath();
      splineThrough(pts, 0.5);
      ctx.stroke();

    } else if(t.type==='straight'){
      if(pts.length<2){ctx.setLineDash([]);return;}
      ctx.beginPath(); ctx.moveTo(pts[0].x,pts[0].y);
      pts.forEach(p=>ctx.lineTo(p.x,p.y));
      ctx.stroke();

    } else if(t.type==='tooth_ui'){
      if(pts.length>=2) drawUpperIncisor(pts[0],pts[1],t.color,t.width);

    } else if(t.type==='tooth_li'){
      if(pts.length>=2) drawLowerIncisor(pts[0],pts[1],t.color,t.width);

    } else if(t.type==='tooth_u6'){
      if(pts.length>=2) drawUpperMolar(pts[0],pts[1],t.color,t.width);

    } else if(t.type==='tooth_l6'){
      if(pts.length>=2) drawLowerMolar(pts[0],pts[1],t.color,t.width);
    }

    ctx.setLineDash([]);
  });
}

function drawPlane(p1,p2,color,extend,name){
  let ax=p1.x,ay=p1.y,bx=p2.x,by=p2.y;
  if(extend){
    const L=3000,dx=bx-ax,dy=by-ay,len=Math.hypot(dx,dy);
    if(len<0.001)return;
    ax-=dx/len*L;ay-=dy/len*L;bx+=dx/len*L;by+=dy/len*L;
  }
  ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);
  ctx.strokeStyle=color;ctx.lineWidth=1.2/view.sc;ctx.stroke();
  // Label midpoint
  if(name){
    const mx=(p1.x+p2.x)/2,my=(p1.y+p2.y)/2;
    const fs=10/view.sc;
    ctx.font=`bold ${fs}px Arial`;
    ctx.fillStyle='rgba(0,0,0,.6)';
    const tw=ctx.measureText(name).width;
    ctx.fillRect(mx-1/view.sc,my-fs,tw+4/view.sc,fs+2/view.sc);
    ctx.fillStyle=color;ctx.fillText(name,mx+1/view.sc,my);
  }
}

function drawLandmarks(){
  const r  = (+document.getElementById('rng-r').value)/view.sc;
  const fs = (+document.getElementById('rng-fs').value)/view.sc;
  const sl = document.getElementById('chk-lbl').checked;
  lms.forEach(lm=>{
    const {x,y}=lm;
    ctx.beginPath();ctx.arc(x,y,r+1.2/view.sc,0,2*Math.PI);ctx.fillStyle='rgba(0,0,0,.7)';ctx.fill();
    ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.fillStyle='#4fc3f7';ctx.fill();
    if(sl){
      const lbl=lblMode==='abbrev'?(ABBREV[lm.id]||String(lm.id)):String(lm.id);
      ctx.font=`bold ${fs}px 'Segoe UI',Arial,sans-serif`;
      const tw=ctx.measureText(lbl).width;
      const tx=x+r+2/view.sc,ty=y-r+fs*.35;
      ctx.fillStyle='rgba(0,0,0,.65)';ctx.fillRect(tx-1/view.sc,ty-fs*.85,tw+4/view.sc,fs+2/view.sc);
      ctx.fillStyle='#c8e6fa';ctx.fillText(lbl,tx+1/view.sc,ty);
    }
  });
}

// ══════════════════════════════════════════════════════════
//  GEOMETRY HELPERS  (anatomical coords: y inverted)
// ══════════════════════════════════════════════════════════
const G  = id => { const l=lms.find(m=>m.id===id); return l?{x:l.x,y:-l.y}:null; };
const V  = (p1,p2) => ({x:p2.x-p1.x, y:p2.y-p1.y});
const mg = v => Math.hypot(v.x,v.y);
const nv = v => { const m=mg(v); return m<1e-6?{x:0,y:0}:{x:v.x/m,y:v.y/m}; };
const dt = (a,b) => a.x*b.x+a.y*b.y;
const cr = (a,b) => a.x*b.y-a.y*b.x;
const ps = () => pixelSpacing;

function angVV(v1,v2){
  const d=dt(nv(v1),nv(v2));
  return Math.acos(Math.max(-1,Math.min(1,d)))*180/Math.PI;
}
function angFH_v(v){
  const Or=G(6),Po=G(16); if(!Or||!Po) return null;
  const fh=V(Po,Or);
  return Math.abs(Math.atan2(cr(fh,v),dt(fh,v)))*180/Math.PI;
}
function ptLine(pt,p1,p2){
  const v=V(p1,p2),w=V(p1,pt),len=mg(v);
  if(len<0.001) return null;
  return cr(v,w)/len*ps();
}

// ══════════════════════════════════════════════════════════
//  MEASUREMENT DISPATCHER
// ══════════════════════════════════════════════════════════
function calcMeas(m){
  switch(m.fn){
    case 'angFH': {
      const p1=G(m.a1),p2=G(m.a2); if(!p1||!p2) return null;
      return angFH_v(V(p1,p2));
    }
    case 'angVV': {
      const p1=G(m.a1),p2=G(m.a2),p3=G(m.b1),p4=G(m.b2);
      if(!p1||!p2||!p3||!p4) return null;
      return angVV(V(p1,p2),V(p3,p4));
    }
    case 'ang3': {
      const A=G(m.a1),B=G(m.a2),C=G(m.a3); if(!A||!B||!C) return null;
      return angVV(V(B,A),V(B,C));
    }
    case 'anb': {
      const s=G(11),n=G(5),a=G(1),b=G(3); if(!s||!n||!a||!b) return null;
      const sna=angVV(V(n,s),V(n,a));
      const snb=angVV(V(n,s),V(n,b));
      return sna-snb;
    }
    case 'dist': {
      const p1=G(m.a1),p2=G(m.a2); if(!p1||!p2) return null;
      return mg(V(p1,p2))*ps();
    }
    case 'ptLine': {
      const pt=G(m.a1),p1=G(m.l1),p2=G(m.l2); if(!pt||!p1||!p2) return null;
      return ptLine(pt,p1,p2);
    }
    case 'ptLineV': {
      // Perpendicular distance to vertical through lm (PtV)
      const pt=G(m.a1),ref=G(m.l1); if(!pt||!ref) return null;
      return (ref.x-pt.x)*ps(); // horizontal distance
    }
    case 'perpFH': {
      // Distance from point to perpendicular to FH through ref point
      const pt=G(m.a1),ref=G(m.ref); if(!pt||!ref) return null;
      return (pt.x-ref.x)*ps();
    }
    case 'ratio': {
      const p1=G(m.a1),p2=G(m.a2),p3=G(m.b1),p4=G(m.b2);
      if(!p1||!p2||!p3||!p4) return null;
      const d1=mg(V(p1,p2)),d2=mg(V(p3,p4));
      return d2<0.001?null:(d1/d2);
    }
    case 'faceRatio': {
      const s=G(11),n=G(5),go=G(15),me=G(4); if(!s||!n||!go||!me) return null;
      return mg(V(s,go))/mg(V(n,me));
    }
    case 'overjet': {
      const ui=G(23),li=G(24); if(!ui||!li) return null;
      return (ui.x-li.x)*ps();
    }
    case 'overbite': {
      const ui=G(23),li=G(24); if(!ui||!li) return null;
      return Math.abs(ui.y-li.y)*ps();
    }
    case 'wits': {
      // Project A and B onto occlusal plane, measure AO-BO
      const a=G(1),b=G(3),oc1=G(23),oc2=G(27); if(!a||!b||!oc1||!oc2) return null;
      const ov=nv(V(oc1,oc2));
      const ao=dt(V(oc1,a),ov)*ps();
      const bo=dt(V(oc1,b),ov)*ps();
      return ao-bo;
    }
    case 'triSum': {
      const fma=calcMeas({fn:'angFH',"a1":15,"a2":4});
      const fmia=calcMeas({fn:'angFH',"a1":22,"a2":24});
      const impa=calcMeas({fn:'angVV',"a1":15,"a2":4,"b1":22,"b2":24});
      if(fma===null||fmia===null||impa===null) return null;
      return fma+fmia+impa;
    }
    case 'sum3ang': {
      const s=calcMeas({fn:'ang3',"a1":5,"a2":11,"a3":12});
      const a=calcMeas({fn:'ang3',"a1":11,"a2":12,"a3":15});
      const g=calcMeas({fn:'ang3',"a1":12,"a2":15,"a3":4});
      if(s===null||a===null||g===null) return null;
      return s+a+g;
    }
    case 'angFH_custom': {
      // angle between vector a1-a2 and b1-b2
      const p1=G(m.a1),p2=G(m.a2),p3=G(m.b1),p4=G(m.b2);
      if(!p1||!p2||!p3||!p4) return null;
      return angVV(V(p1,p2),V(p3,p4));
    }
    default: return null;
  }
}

function computeAnalysis(analName){
  const anal=ANALYSES[analName]; if(!anal) return [];
  return anal.measurements.map(m=>{
    const val=calcMeas(m);
    const diff=val===null?null:+(val-m.norm).toFixed(2);
    const u=m.unit;
    const cls=val===null?'na':Math.abs(diff)<=m.sd?'ok':diff>m.sd?'hi':'lo';
    let evalText=null;
    if(val!==null&&m.evalLow&&m.evalHigh){
      if(cls==='lo') evalText=m.evalLow;
      else if(cls==='hi') evalText=m.evalHigh;
      else evalText='Normal';
    }
    return {
      nr:m.nr, param:m.param, info:m.info||'',
      val:val===null?null:+val.toFixed(2),
      norm:m.norm, sd:m.sd, unit:u,
      diff,
      valStr:val===null?'—':val.toFixed(u==='°'||u==='%'?1:2)+u,
      normStr:`${m.norm}±${m.sd}${u}`,
      diffStr:diff===null?'—':(diff>=0?'+':'')+diff.toFixed(2)+u,
      cls, eval:evalText,
      graphPct:val===null?0:Math.max(-100,Math.min(100,((val-m.norm)/(m.sd||1))*25)),
    };
  });
}

// ══════════════════════════════════════════════════════════
//  SIDE PANEL BUILDER
// ══════════════════════════════════════════════════════════
function buildSidePanel(){
  buildAnalysisSelector();
  buildTracingPanel();
  buildPlanePanel();
  updateAnalysisTable();
}

function buildAnalysisSelector(){
  const el=document.getElementById('anal-sel');
  el.innerHTML='<option value="">— Sélectionner une analyse —</option>';
  Object.keys(ANALYSES).forEach(name=>{
    const opt=document.createElement('option');
    opt.value=name; opt.textContent=name;
    el.append(opt);
  });
  el.value=activeAnalysis;
}

function setAnalysis(name){
  activeAnalysis=name;
  planeVis={};
  const anal=ANALYSES[name];
  if(anal) anal.planes.forEach(p=>{ planeVis[p.id]=false; });
  buildPlanePanel();
  updateAnalysisTable();
  R();
  setSt('Analyse: '+name);
}

function buildTracingPanel(){
  const el=document.getElementById('trc-panel');
  el.innerHTML='';
  ANATOMICAL.forEach(t=>{
    const row=document.createElement('div');
    row.style.cssText='display:flex;align-items:center;gap:5px;margin-bottom:3px;';
    const chk=document.createElement('input'); chk.type='checkbox'; chk.checked=tracingVis[t.id];
    chk.onchange=()=>{ tracingVis[t.id]=chk.checked; R(); };
    const sw=document.createElement('div');
    sw.style.cssText=`width:10px;height:10px;border-radius:2px;background:${t.color};flex-shrink:0;`;
    const lbl=document.createElement('label'); lbl.style.cssText='font-size:11px;color:#c0cce0;cursor:pointer;';
    lbl.textContent=t.name; lbl.onclick=()=>{ chk.checked=!chk.checked; tracingVis[t.id]=chk.checked; R(); };
    row.append(chk,sw,lbl); el.append(row);
  });
}

function buildPlanePanel(){
  const el=document.getElementById('pln-panel');
  el.innerHTML='';
  const anal=ANALYSES[activeAnalysis]; if(!anal){el.textContent='—';return;}
  anal.planes.forEach(pl=>{
    const row=document.createElement('div');
    row.style.cssText='display:flex;align-items:center;gap:5px;margin-bottom:3px;';
    const chk=document.createElement('input'); chk.type='checkbox'; chk.checked=planeVis[pl.id]!==false;
    chk.onchange=()=>{ planeVis[pl.id]=chk.checked; R(); };
    const sw=document.createElement('div');
    sw.style.cssText=`width:10px;height:10px;border-radius:2px;background:${pl.color};flex-shrink:0;`;
    const lbl=document.createElement('label'); lbl.style.cssText='font-size:11px;color:#c0cce0;cursor:pointer;';
    lbl.textContent=pl.name; lbl.onclick=()=>{ chk.checked=!chk.checked; planeVis[pl.id]=chk.checked; R(); };
    row.append(chk,sw,lbl); el.append(row);
  });
}

function updateAnalysisTable(){
  const res=computeAnalysis(activeAnalysis);
  const tbody=document.getElementById('atbody'); tbody.innerHTML='';
  res.forEach(r=>{
    const tr=document.createElement('tr'); tr.className=r.cls;
    const colVal=r.cls==='ok'?'#88cc88':r.cls==='hi'?'#ff7777':'#ff7777';
    const graphW=40, ctr=20, oneSigmaPx=10;
    const barW=Math.max(2,Math.min(ctr,Math.abs(r.graphPct)/100*ctr));
    const barColor=r.graphPct>0?'#ff7777':'#77aaff';
    const infoShort=r.info?r.info.split('.')[0]:'';
    tr.innerHTML=`<td><div style="font-weight:600;font-size:10px">${r.param}</div>`+
      (r.info?`<div style="font-size:8px;color:#889;line-height:1.2;margin-top:1px">${infoShort.length>45?infoShort.substr(0,43)+'…':infoShort}</div>`:'')+
      `</td>`+
      `<td>${r.norm}</td>`+
      `<td>${r.sd}</td>`+
      `<td style="color:${colVal};font-weight:700">${r.valStr}</td>`+
      `<td style="text-align:center"><div style="display:inline-flex;align-items:center;gap:1px;justify-content:center">`+
        `<div style="width:${graphW}px;height:14px;background:#1a1f38;border-radius:3px;position:relative;overflow:hidden">`+
          `<div style="position:absolute;top:0;left:${ctr-oneSigmaPx}px;width:${oneSigmaPx*2}px;height:14px;background:rgba(100,200,100,0.12);border-radius:1px"></div>`+
          `<div style="position:absolute;top:0;left:${ctr-0.5}px;width:1px;height:14px;background:#55bb55"></div>`+
          `<div style="position:absolute;top:2px;${r.graphPct>=0?`left:${ctr}px`:`right:${graphW-ctr}px`};width:${barW}px;height:10px;background:${barColor};border-radius:1px;opacity:0.85"></div>`+
        `</div>`+
      `</div></td>`+
      `<td><div style="font-weight:600;font-size:10px">${r.eval||'—'}</div>`+
        (r.eval&&r.eval!=='Normal'?`<div style="font-size:8px;color:#889;line-height:1.2;margin-top:1px">Écart: ${r.diffStr}</div>`:'')+
      `</td>`;
    tbody.append(tr);
  });
}

// ══════════════════════════════════════════════════════════
//  MOUSE / TOUCH EVENTS
// ══════════════════════════════════════════════════════════
function sToI(sx,sy){ return [(sx-view.tx)/view.sc,(sy-view.ty)/view.sc]; }
function hit(ix,iy){
  const hr=(+document.getElementById('rng-r').value)/view.sc+8/view.sc;
  for(let i=lms.length-1;i>=0;i--){
    const dx=ix-lms[i].x,dy=iy-lms[i].y;
    if(dx*dx+dy*dy<=hr*hr) return i;
  }
  return -1;
}
function evXY(e){ const r=canvas.getBoundingClientRect(),t=e.touches?e.touches[0]:e; return [t.clientX-r.left,t.clientY-r.top]; }

canvas.addEventListener('contextmenu',e=>{
  e.preventDefault();
  if(currentTrace&&currentTrace.pts.length>=2){ customTraces.push({...currentTrace}); currentTrace=null; colorIdx++; R(); setSt('Tracé terminé.'); }
});

canvas.addEventListener('mousedown',e=>{
  const [sx,sy]=evXY(e);
  const [ix,iy]=sToI(sx,sy);
  if(e.button===1||e.altKey){ isPan=true; panStart={sx,sy}; viewStart={...view}; canvas.style.cursor='grab'; e.preventDefault(); return; }
  if(e.button===2) return;

  if(calibState==='pt1'){ calibPt1={x:ix,y:iy}; calibState='pt2'; setSt('Cliquez le 2e point de la règle'); R(); return; }
  if(calibState==='pt2'){
    const d=Math.hypot(ix-calibPt1.x,iy-calibPt1.y);
    const mm=parseFloat(prompt('Distance entre les 2 points (mm) ?','20'));
    if(mm&&d>0){ pixelSpacing=mm/d; document.getElementById('pxmm').textContent=(1/pixelSpacing).toFixed(2); setSt(`Calibration OK: 1px=${pixelSpacing.toFixed(4)}mm`); updateAnalysisTable(); }
    calibState=null; calibPt1=null; R(); return;
  }

  if(mode==='sel'){
    const idx=hit(ix,iy);
    if(idx>=0){ drag={idx,ox:ix-lms[idx].x,oy:iy-lms[idx].y}; canvas.style.cursor='grabbing'; }
  } else if(mode==='trc'){
    if(!currentTrace) currentTrace={pts:[],color:TC[colorIdx%TC.length]};
    currentTrace.pts.push({x:ix,y:iy}); R();
    setSt(`Tracé: ${currentTrace.pts.length} pts — clic droit pour terminer`);
  } else if(mode==='pln'){
    drawingPlane={x1:ix,y1:iy,x2:ix,y2:iy,color:TC[(colorIdx+2)%TC.length]};
  } else if(mode==='era'){
    if(customPlanes.length>0){customPlanes.pop();R();setSt('Plan supprimé.');}
    else if(customTraces.length>0){customTraces.pop();R();setSt('Tracé supprimé.');}
  }
  e.preventDefault();
});

canvas.addEventListener('mousemove',e=>{
  const [sx,sy]=evXY(e);
  const [ix,iy]=sToI(sx,sy);
  if(isPan){ view.tx=viewStart.tx+(sx-panStart.sx); view.ty=viewStart.ty+(sy-panStart.sy); R(); return; }
  if(drag!==null){
    lms[drag.idx].x=ix-drag.ox; lms[drag.idx].y=iy-drag.oy;
    R(); updateAnalysisTable();
    setSt(`${ABBREV[lms[drag.idx].id]||lms[drag.idx].id} → (${(ix-drag.ox).toFixed(0)},${(iy-drag.oy).toFixed(0)})px`);
    return;
  }
  if(drawingPlane){ drawingPlane.x2=ix; drawingPlane.y2=iy; R(); return; }
  if(mode==='sel'){
    const idx=hit(ix,iy);
    if(idx>=0){
      canvas.style.cursor='grab';
      const lm=lms[idx];
      tip.style.cssText=`display:block;left:${sx+14}px;top:${sy-10}px`;
      tip.textContent=`${ABBREV[lm.id]||lm.id} — ${LM_NAMES[lm.id]||''} (${lm.x.toFixed(0)},${lm.y.toFixed(0)})`;
    } else { canvas.style.cursor='crosshair'; tip.style.display='none'; }
  }
});

canvas.addEventListener('mouseup',e=>{
  if(isPan){ isPan=false; canvas.style.cursor='crosshair'; return; }
  if(drag!==null){
    const lm=lms[drag.idx];
    setSt(`✅ ${ABBREV[lm.id]||lm.id} → (${lm.x.toFixed(0)},${lm.y.toFixed(0)})px`);
    drag=null; canvas.style.cursor='crosshair'; updateAnalysisTable();
  }
  if(drawingPlane&&Math.hypot(drawingPlane.x2-drawingPlane.x1,drawingPlane.y2-drawingPlane.y1)>5){
    customPlanes.push({...drawingPlane}); colorIdx++; setSt('Plan ajouté.');
  }
  drawingPlane=null; R();
});

canvas.addEventListener('mouseleave',()=>{ drag=null; isPan=false; tip.style.display='none'; drawingPlane=null; });

canvas.addEventListener('wheel',e=>{
  e.preventDefault();
  zoom(e.deltaY<0?1.12:0.89,e.offsetX,e.offsetY);
},{passive:false});

window.addEventListener('keydown',e=>{if(e.code==='Space'){isPan=true;canvas.style.cursor='grab';e.preventDefault();}});
window.addEventListener('keyup',  e=>{if(e.code==='Space'){isPan=false;canvas.style.cursor='crosshair';}});

// ══════════════════════════════════════════════════════════
//  UI HELPERS
// ══════════════════════════════════════════════════════════
function setMode(m){
  mode=m;
  ['sel','trc','pln','era'].forEach(x=>document.getElementById('bm-'+x).className='btn '+(x===m?'on':'off'));
  if(m!=='trc'&&currentTrace){customTraces.push({...currentTrace});currentTrace=null;colorIdx++;R();}
  const help={sel:'Sélection: glissez les points',trc:'Tracé: clic = point, clic droit = fin',pln:'Plan: cliquez-glissez',era:'Effacer: dernier élément'};
  setSt(help[m]||m);
}
function setLblMode(m){
  lblMode=m;
  document.getElementById('bl-abr').className='btn '+(m==='abbrev'?'on':'off');
  document.getElementById('bl-num').className='btn '+(m==='number'?'on':'off');
  R();
}
function setSt(msg){ stEl.textContent=msg; }
function resetPts(){ lms=JSON.parse(JSON.stringify(INIT_LMS)); customTraces=[]; customPlanes=[]; currentTrace=null; updateAnalysisTable(); R(); setSt('Réinitialisé.'); }
function startCalib(){ calibState='pt1'; calibPt1=null; setSt('Calibration: cliquez le 1er point de la règle.'); }
function getLM(id){ return lms.find(l=>l.id===id)||null; }

// Section collapse toggle
function toggleSec(h4){ h4.parentElement.classList.toggle('collapsed'); }

// All tracings + Select all / none
function toggleAllTracings(v){ Object.keys(tracingVis).forEach(k=>tracingVis[k]=v); buildTracingPanel(); R(); }
function toggleAllPlanes(v){ Object.keys(planeVis).forEach(k=>planeVis[k]=v); buildPlanePanel(); R(); }

// ══════════════════════════════════════════════════════════
//  EXPORTS
// ══════════════════════════════════════════════════════════
function renderHD(){
  const tc=document.createElement('canvas');
  tc.width=img.naturalWidth; tc.height=img.naturalHeight;
  const x=tc.getContext('2d');
  const br=document.getElementById('rng-br').value;
  const ct=document.getElementById('rng-ct').value;
  x.filter=`brightness(${br}%) contrast(${ct}%)`; x.drawImage(img,0,0); x.filter='none';
  // Tracings HD — reuse spline/tooth helpers via an offscreen-ctx proxy
  // We temporarily swap ctx→x for the shared drawing functions
  const _ctx=ctx; // save live ctx
  // Override ctx for HD drawing (the helper functions use `ctx` global)
  // Simpler: inline HD tracing with same logic
  ANATOMICAL.forEach(t=>{
    if(!tracingVis[t.id]) return;
    const pts=t.lms.map(id=>getLM(id)).filter(Boolean);
    x.strokeStyle=t.color; x.lineWidth=t.width*2;
    if(t.type==='spline'){
      if(pts.length<2) return;
      // Catmull-Rom in HD ctx
      const ext=[pts[0],...pts,pts[pts.length-1]];
      x.beginPath(); x.moveTo(pts[0].x,pts[0].y);
      for(let i=0;i<pts.length-1;i++){
        const p0=ext[i],p1=ext[i+1],p2=ext[i+2],p3=ext[i+3]||ext[ext.length-1];
        const s=0.5;
        x.bezierCurveTo(p1.x+(p2.x-p0.x)*s/3,p1.y+(p2.y-p0.y)*s/3,
                        p2.x-(p3.x-p1.x)*s/3,p2.y-(p3.y-p1.y)*s/3,p2.x,p2.y);
      }
      x.stroke();
    } else if(t.type==='straight'){
      if(pts.length<2) return;
      x.beginPath();x.moveTo(pts[0].x,pts[0].y);pts.forEach(p=>x.lineTo(p.x,p.y));x.stroke();
    } else if(t.type==='tooth_ui'){
      if(pts.length>=2) drawUpperIncisorOnCtx(x,pts[0],pts[1]);
    } else if(t.type==='tooth_li'){
      if(pts.length>=2) drawLowerIncisorOnCtx(x,pts[0],pts[1]);
    } else if(t.type==='tooth_u6'){
      if(pts.length>=2) drawUpperMolarOnCtx(x,pts[0],pts[1]);
    } else if(t.type==='tooth_l6'){
      if(pts.length>=2) drawLowerMolarOnCtx(x,pts[0],pts[1]);
    }
  });

  // Planes
  const anal=ANALYSES[activeAnalysis];
  if(anal) anal.planes.forEach(pl=>{
    if(planeVis[pl.id]===false) return;
    const p1=getLM(pl.lm1),p2=getLM(pl.lm2); if(!p1||!p2) return;
    let ax=p1.x,ay=p1.y,bx=p2.x,by=p2.y;
    if(pl.ext){const L=3000,dx=bx-ax,dy=by-ay,len=Math.hypot(dx,dy);ax-=dx/len*L;ay-=dy/len*L;bx+=dx/len*L;by+=dy/len*L;}
    x.beginPath();x.moveTo(ax,ay);x.lineTo(bx,by);x.strokeStyle=pl.color;x.lineWidth=1.5;x.stroke();
    if(pl.name){
      x.font='bold 18px Segoe UI,Arial';x.fillStyle=pl.color;
      x.fillText(pl.name,(p1.x+p2.x)/2+5,(p1.y+p2.y)/2-5);
    }
  });
  customPlanes.forEach(pl=>{x.beginPath();x.moveTo(pl.x1,pl.y1);x.lineTo(pl.x2,pl.y2);x.strokeStyle=pl.color;x.lineWidth=2;x.stroke();});
  customTraces.forEach(tr=>{
    if(tr.pts.length<2)return;
    x.beginPath();x.moveTo(tr.pts[0].x,tr.pts[0].y);tr.pts.slice(1).forEach(p=>x.lineTo(p.x,p.y));
    x.strokeStyle=tr.color;x.lineWidth=2;x.stroke();
  });
  // Landmarks
  const sl=document.getElementById('chk-lbl').checked;
  const r=8, fs=18;
  lms.forEach(lm=>{
    x.beginPath();x.arc(lm.x,lm.y,r+1.5,0,2*Math.PI);x.fillStyle='rgba(0,0,0,.7)';x.fill();
    x.beginPath();x.arc(lm.x,lm.y,r,0,2*Math.PI);x.fillStyle='#4fc3f7';x.fill();
    if(sl){
      const lbl=lblMode==='abbrev'?(ABBREV[lm.id]||String(lm.id)):String(lm.id);
      x.font=`bold ${fs}px Segoe UI,Arial`;
      const tw=x.measureText(lbl).width;
      const tx=lm.x+r+3,ty=lm.y-r+fs*.35;
      x.fillStyle='rgba(0,0,0,.65)';x.fillRect(tx-1,ty-fs*.85,tw+4,fs+2);
      x.fillStyle='#c8e6fa';x.fillText(lbl,tx+1,ty);
    }
  });
  return tc;
}

function dlPNG(){
  const tc=renderHD();
  const a=document.createElement('a');a.download='ceph_annotated.png';a.href=tc.toDataURL('image/png');a.click();
  setSt('✅ PNG exporté.');
}
function dlJSON(){
  const d={image_width:img.naturalWidth,image_height:img.naturalHeight,landmarks:lms,analysis:activeAnalysis,results:computeAnalysis(activeAnalysis)};
  const a=document.createElement('a');a.download='ceph_analysis.json';
  a.href=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}));a.click();
  setSt('✅ JSON exporté.');
}

async function dlPDF(){
  if(typeof window.jspdf==='undefined'){setSt('⏳ Chargement jsPDF…');await new Promise(r=>setTimeout(r,1500));}
  const {jsPDF}=window.jspdf;
  const doc=new jsPDF({orientation:'portrait',unit:'mm',format:'a4'});
  const W=210,H=297;

  // ── P1: image ──
  doc.setFillColor(14,17,23);doc.rect(0,0,W,H,'F');
  doc.setFontSize(13);doc.setTextColor(200,220,255);
  doc.text('Analyse Céphalométrique — '+activeAnalysis,W/2,11,{align:'center'});
  doc.setFontSize(8);doc.setTextColor(120,150,200);
  doc.text(new Date().toLocaleDateString('fr-FR'),W/2,17,{align:'center'});
  const tc=renderHD();
  const iw=tc.width,ih=tc.height;
  const sc2=Math.min((W-20)/iw,(H-30)/ih);
  doc.addImage(tc.toDataURL('image/jpeg',0.88),'JPEG',(W-iw*sc2)/2,20,iw*sc2,ih*sc2);

  // ── P2: table ──
  doc.addPage();
  doc.setFillColor(14,17,23);doc.rect(0,0,W,H,'F');
  doc.setFontSize(12);doc.setTextColor(200,220,255);
  doc.text('Mesures — Analyse de '+activeAnalysis,W/2,11,{align:'center'});
  doc.setFontSize(7);doc.setTextColor(100,130,160);
  doc.text(`Pixel spacing: ${pixelSpacing.toFixed(4)} mm/px  |  Date: ${new Date().toLocaleDateString('fr-FR')}`,15,17);

  const res=computeAnalysis(activeAnalysis);
  const cx=[14, 21, 115, 143, 165, 189];
  doc.setFillColor(25,32,55);doc.rect(12,20,W-24,7,'F');
  doc.setFontSize(7.5);doc.setTextColor(130,160,210);
  ['#','Paramètre','Valeur','Référence','Δ','Commentaire'].forEach((h,i)=>doc.text(h,cx[i],25.5));
  let yy=32;
  res.forEach(r=>{
    if(yy>H-10){doc.addPage();doc.setFillColor(14,17,23);doc.rect(0,0,W,H,'F');yy=15;}
    const bg=r.cls==='ok'?[18, 38, 22]:r.cls==='hi'?[40, 18, 18]:r.cls==='lo'?[38, 28, 14]:[14, 17, 23];
    doc.setFillColor(...bg);doc.rect(12,yy-4,W-24,6,'F');
    doc.setFontSize(7);doc.setTextColor(180,200,235);
    doc.text(String(r.nr),cx[0],yy);
    doc.text(r.param.length>33?r.param.substr(0,31)+'…':r.param,cx[1],yy);
    const vc=r.cls==='ok'?[150, 230, 150]:r.cls==='hi'?[240, 130, 130]:[230, 180, 100];
    doc.setTextColor(...vc);doc.setFontSize(8);doc.text(r.valStr,cx[2],yy);
    doc.setTextColor(130,150,180);doc.setFontSize(7);doc.text(r.normStr,cx[3],yy);
    const dc=r.diff===null?[100, 100, 100]:Math.abs(r.diff)<=r.sd?[100, 200, 100]:r.diff>r.sd?[230, 100, 100]:[230, 160, 80];
    doc.setTextColor(...dc);doc.text(r.diffStr,cx[4],yy);
    yy+=6.5;
  });
  doc.save(`ceph_${activeAnalysis.toLowerCase()}.pdf`);
  setSt('✅ PDF exporté.');
}
"""


# ─────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#0e1117;font-family:'Segoe UI',sans-serif;color:#e0e0e0;display:flex;flex-direction:column;height:100vh;overflow:hidden;}
#tb{display:flex;flex-wrap:wrap;gap:5px;align-items:center;padding:5px 8px;background:#161b2e;border-bottom:1px solid #2a2f4a;flex-shrink:0;}
.tg{display:flex;align-items:center;gap:4px;background:#1e2440;border-radius:5px;padding:3px 7px;}
.tg label{font-size:11px;color:#8899bb;white-space:nowrap;}
.btn{padding:3px 8px;border-radius:4px;border:none;cursor:pointer;font-size:11px;font-weight:700;transition:all .15s;}
.btn.on{background:#4f8ef7;color:#fff;}.btn.off{background:#2a2f4a;color:#8899bb;}
.btn.g{background:#2d6a4f;color:#a0e0b0;}.btn.g:hover{background:#3a8a62;}
.btn.r{background:#6a2d2d;color:#e0a0a0;}.btn.r:hover{background:#8a3a3a;}
.btn.o{background:#6a4e2d;color:#e0c0a0;}.btn.o:hover{background:#8a622d;}
input[type=range]{width:70px;accent-color:#4f8ef7;cursor:pointer;}
input[type=checkbox]{accent-color:#4f8ef7;width:13px;height:13px;cursor:pointer;}
.vd{font-size:11px;color:#7eb3ff;min-width:22px;text-align:center;}
#main{display:flex;flex:1;overflow:hidden;}
#cv{position:relative;flex:1;overflow:hidden;background:#000;cursor:crosshair;}
canvas{display:block;position:absolute;top:0;left:0;}
#tip{position:absolute;pointer-events:none;display:none;background:rgba(10,12,28,.93);border:1px solid #4f8ef7;border-radius:5px;padding:4px 9px;font-size:11px;color:#fff;white-space:nowrap;z-index:10;}
#side{width:40%;min-width:320px;max-width:70%;background:#161b2e;border-left:1px solid #2a2f4a;overflow:auto;flex-shrink:0;display:flex;flex-direction:column;resize:horizontal;}
.sec{border-bottom:1px solid #2a2f4a;padding:7px 8px;}
.sec h4{font-size:11px;font-weight:700;color:#7eb3ff;margin-bottom:5px;text-transform:uppercase;letter-spacing:.05em;display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;}
.sec h4 .sa{display:flex;gap:3px;}
.sec h4 .sa button{font-size:9px;padding:1px 5px;border:none;border-radius:3px;cursor:pointer;background:#2a2f4a;color:#8899bb;}
.sec h4 .toggle-icon{font-size:9px;color:#556;margin-right:4px;transition:transform .15s;}
.sec.collapsed h4 .toggle-icon{transform:rotate(-90deg);}
.sec-body{overflow:visible;}
.sec.collapsed .sec-body{display:none;}
#anal-sel{max-height:220px;overflow-y:auto;}
.atbl{width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed;}
.atbl th{background:#1e2440;color:#8899bb;padding:4px 3px;text-align:center;font-weight:600;white-space:nowrap;}
.atbl th:first-child{width:30%;}
.atbl th:nth-child(2){width:8%;},
.atbl th:nth-child(3){width:8%;}
.atbl th:nth-child(4){width:8%;}
.atbl th:nth-child(5){width:11%;}
.atbl th:last-child{width:35%;}
.atbl td{padding:3px 3px;border-bottom:1px solid #1a1f38;text-align:center;vertical-align:middle;}
.atbl td:first-child{text-align:left;}
.atbl td:nth-child(2),
.atbl td:nth-child(3){}
.atbl td:nth-child(4){font-weight:700;}
.atbl td:nth-child(5){}
.atbl td:last-child{text-align:left;font-size:10px;white-space:normal;word-break:break-word;}
.atbl tr.ok td{color:#a0d0a0;}.atbl tr.hi td{color:#ff8888;}.atbl tr.lo td{color:#ffaa66;}.atbl tr.na td{color:#555;}
#sb{display:flex;gap:6px;align-items:center;padding:5px 8px;background:#161b2e;border-top:1px solid #2a2f4a;flex-shrink:0;flex-wrap:wrap;}
.sbtn{padding:3px 10px;border-radius:4px;border:none;cursor:pointer;font-size:11px;font-weight:700;}
#st{font-size:11px;color:#7eb3ff;margin-left:auto;}
</style>
</head>
<body>
<div id="tb">
  <div class="tg"><label>Mode</label>
    <button class="btn on"  id="bm-sel" onclick="setMode('sel')">✥ Sélect.</button>
    <button class="btn off" id="bm-trc" onclick="setMode('trc')">✏ Tracé</button>
    <button class="btn off" id="bm-pln" onclick="setMode('pln')">⟵ Plan</button>
    <button class="btn off" id="bm-era" onclick="setMode('era')">✕ Eff.</button>
  </div>
  <div class="tg"><label>Labels</label>
    <button class="btn on"  id="bl-abr" onclick="setLblMode('abbrev')">Abrév.</button>
    <button class="btn off" id="bl-num" onclick="setLblMode('number')">N°</button>
    <input type="checkbox" id="chk-lbl" checked onchange="R()">
    <label style="font-size:10px;color:#8899bb">Afficher</label>
  </div>
  <div class="tg"><label>Police</label>
    <input type="range" id="rng-fs" min="8" max="36" value="12" oninput="document.getElementById('vfs').textContent=this.value;R()">
    <span class="vd" id="vfs">12</span>
  </div>
  <div class="tg"><label>Rayon</label>
    <input type="range" id="rng-r" min="2" max="18" value="5" oninput="document.getElementById('vr').textContent=this.value;R()">
    <span class="vd" id="vr">5</span>
  </div>
  <div class="tg"><label>Luminosité</label>
    <input type="range" id="rng-br" min="20" max="300" value="100" oninput="document.getElementById('vbr').textContent=this.value+'%';R()">
    <span class="vd" id="vbr">100%</span>
  </div>
  <div class="tg"><label>Contraste</label>
    <input type="range" id="rng-ct" min="20" max="400" value="100" oninput="document.getElementById('vct').textContent=this.value+'%';R()">
    <span class="vd" id="vct">100%</span>
  </div>
  <div class="tg">
    <button class="btn off" onclick="fitView()">⤢ Fit</button>
    <button class="btn off" onclick="zoom(1.2)">＋</button>
    <button class="btn off" onclick="zoom(0.8)">－</button>
  </div>
  <div class="tg">
    <button class="btn o" onclick="startCalib()">📏 Calibrer</button>
    <span style="font-size:10px;color:#e0c080">px/mm: <span id="pxmm">auto</span></span>
  </div>
</div>
<div id="main">
  <div id="cv"><canvas id="mc"></canvas><div id="tip"></div></div>
  <div id="side">
    <div class="sec">
      <h4 onclick="toggleSec(this)"><span class="toggle-icon">▼</span>📊 Analyse
        <span class="sa"></span>
      </h4>
      <div class="sec-body">
        <select id="anal-sel" onchange="setAnalysis(this.value)" style="width:100%;background:#1e2440;color:#c0cce0;border:1px solid #2a2f4a;border-radius:4px;padding:4px;font-size:12px;margin-bottom:8px"></select>
        <div style="font-size:9px;color:#556;margin-bottom:4px">
          <span style="color:#a0d0a0">●</span> normal &nbsp;
          <span style="color:#ff8888">●</span> élevé &nbsp;
          <span style="color:#ffaa66">●</span> bas
        </div>
        <table class="atbl">
          <thead><tr><th>Paramètre</th><th>Norme</th><th>±σ</th><th>Valeur</th><th>Graphique</th><th>Évaluation</th></tr></thead>
          <tbody id="atbody"></tbody>
        </table>
      </div>
    </div>
    <div class="sec">
      <h4 onclick="toggleSec(this)"><span class="toggle-icon">▼</span>📐 Plans actifs
        <span class="sa">
          <button onclick="event.stopPropagation();toggleAllPlanes(true)">Tout</button>
          <button onclick="event.stopPropagation();toggleAllPlanes(false)">Aucun</button>
        </span>
      </h4>
      <div class="sec-body"><div id="pln-panel"></div></div>
    </div>
    <div class="sec">
      <h4 onclick="toggleSec(this)"><span class="toggle-icon">▼</span>🦴 Tracés anatomiques
        <span class="sa">
          <button onclick="event.stopPropagation();toggleAllTracings(true)">Tout</button>
          <button onclick="event.stopPropagation();toggleAllTracings(false)">Aucun</button>
        </span>
      </h4>
      <div class="sec-body"><div id="trc-panel"></div></div>
    </div>
    <div class="sec" style="flex:1">
      <h4 onclick="toggleSec(this)"><span class="toggle-icon">▼</span>📋 Résultats</h4>
      <div class="sec-body"><p style="font-size:11px;color:#556">Sélectionnez une analyse ci-dessus.</p></div>
    </div>
  </div>
</div>
<div id="sb">
  <button class="sbtn btn g" onclick="dlPNG()">⬇ PNG</button>
  <button class="sbtn btn off" onclick="dlJSON()">⬇ JSON</button>
  <button class="sbtn btn off" onclick="dlPDF()">⬇ PDF</button>
  <button class="sbtn btn r" onclick="resetPts()">↺ Reset</button>
  <span id="st">Prêt</span>
</div>
<script>
__JS_ENGINE__
</script>
</body>
</html>"""


def build_canvas_html(img_gray, landmarks, settings, lm_mapping):
    """lm_mapping : dict {id(int) -> {"abbr":str, "name":str}}"""
    img_rgb = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
    _, buf  = cv2.imencode(".png", img_rgb)
    img_b64 = base64.b64encode(buf.tobytes()).decode()

    abbrev_map = {k: v["abbr"] for k, v in lm_mapping.items()}
    name_map   = {k: v["name"] for k, v in lm_mapping.items()}

    injected = (
        'const IMG_B64        = "' + img_b64 + '";\n'
        'const INIT_LMS       = ' + json.dumps(landmarks) + ';\n'
        'const ABBREV         = ' + json.dumps(abbrev_map) + ';\n'
        'const LM_NAMES       = ' + json.dumps(name_map) + ';\n'
        'const ANATOMICAL     = ' + json.dumps(ANATOMICAL_TRACINGS) + ';\n'
        'const ANALYSES       = ' + json.dumps(ANALYSES_DEF) + ';\n'
        'const INIT_LBL_MODE  = "' + settings.get("label_mode","number") + '";\n'
        'const INIT_PS        = ' + str(settings.get("pixel_spacing",0.1)) + ';\n'
    )

    js = JS_ENGINE.replace("__INJECTED_DATA__", injected)
    html = HTML_TEMPLATE.replace("__JS_ENGINE__", js)
    return html


# ─────────────────────────────────────────────────────────────────
# LISTE COMPLÈTE DE TOUS LES LANDMARKS POSSIBLES
# ─────────────────────────────────────────────────────────────────
ALL_LM_OPTIONS = {
    # Ricketts
    "S":    "Sella",
    "N":    "Nasion",
    "Or":   "Orbitale",
    "Po":   "Porion",
    "A":    "Point A (Subspinale)",
    "B":    "Point B (Supramentale)",
    "Pog":  "Pogonion",
    "Me":   "Menton",
    "Gn":   "Gnathion",
    "Go":   "Gonion",
    "CF":   "Centre de la Face",
    "PT":   "Point PT (Ptérygoïde)",
    "Ar":   "Articulare",
    "DC":   "Point DC",
    "Ba":   "Basion",
    "ANS":  "Épine Nasale Antérieure",
    "PNS":  "Épine Nasale Postérieure",
    "Xi":   "Point Xi",
    "PM":   "Protuberance Menti",
    "Ui":   "Incisive Sup. (bord incisif)",
    "Li":   "Incisive Inf. (bord incisif)",
    "Ua":   "Incisive Sup. (apex)",
    "La":   "Incisive Inf. (apex)",
    "U6":   "Molaire Sup. (mésial)",
    "Pn":   "Pronasal (pointe du nez)",
    "Ul":   "Lèvre Supérieure",
    "Ll":   "Lèvre Inférieure",
    "Pog'": "Pogonion (tissus mous)",
    "Co":   "Condylion",
    # Steiner / autres
    "D":    "Point D (centre symphyse)",
    "T":    "Point T",
    "R1":   "R1",
    "R2":   "R2",
    "R3":   "R3",
    "R4":   "R4",
    "SnA":  "Subnasale A",
    "SnP":  "Subnasale P",
    "U1r":  "Incisive Sup. root",
    "L1r":  "Incisive Inf. root",
    "L6m":  "Molaire Inf. mésial",
    "Sn":   "Subnasale",
    "Cm":   "Columelle",
    "?":    "Non identifié",
}

# Options pour selectbox : liste triée "ABBR — Nom complet"
LM_SELECT_OPTIONS = ["?  — Non identifié"] + sorted(
    [f"{ab}  — {nm}" for ab, nm in ALL_LM_OPTIONS.items() if ab != "?"],
    key=lambda x: x.split("—")[0].strip()
)

def abbr_from_option(opt: str) -> str:
    return opt.split("—")[0].strip()

def name_from_abbr(abbr: str) -> str:
    return ALL_LM_OPTIONS.get(abbr, abbr)

def default_option_for_id(lm_id: int) -> str:
    meta = LM_META.get(lm_id, {"abbr":"?","name":"Non identifié"})
    abbr = meta["abbr"]
    for opt in LM_SELECT_OPTIONS:
        if abbr_from_option(opt) == abbr:
            return opt
    return LM_SELECT_OPTIONS[0]


# ─────────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────────
def call_predict(img_bytes, filename):
    r = requests.post(f"{API_URL}/predict",
                      files={"file":(filename,img_bytes,"image/png")},
                      timeout=120)
    r.raise_for_status()
    return r.json()

def check_health():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.json() if r.ok else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ceph Analysis", page_icon="🦷", layout="wide")

# ── Initialisation session_state ──────────────────────────────────
if "lm_mapping" not in st.session_state:
    # mapping par défaut (peut être entièrement redéfini par l'utilisateur)
    st.session_state.lm_mapping = {
        i: {"abbr": LM_META[i]["abbr"], "name": LM_META[i]["name"]}
        for i in range(1, 30)
    }
if "mapping_selections" not in st.session_state:
    st.session_state.mapping_selections = {
        i: default_option_for_id(i) for i in range(1, 30)
    }

# ── SIDEBAR ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Paramètres")
    api_url = st.text_input("URL de l'API", value=API_URL)
    if api_url != API_URL:
        API_URL = api_url

    st.divider()
    health = check_health()
    if health:
        st.success("🟢 API connectée")
        st.caption(f"Modèle: `{health.get('model_path','—')}`")
        if not health.get("model_loaded"): st.warning("⚠️ Modèle non chargé")
    else:
        st.error("🔴 API inaccessible")

    st.divider()
    st.subheader("🎨 Affichage")
    init_lbl = st.radio("Labels", ["number","abbrev"],
                         format_func=lambda x:"Numéros" if x=="number" else "Abréviations",
                         horizontal=True,
                         help="Commencez par 'Numéros' pour identifier les points")
    ps = st.number_input("Pixel spacing (mm/px)", value=0.1,
                          min_value=0.001, max_value=2.0,
                          step=0.001, format="%.3f")

    # ── Mapping éditeur ──────────────────────────────────────────
    st.divider()
    st.subheader("🗺️ Mapping des landmarks")
    st.caption(
        "**Étape 1** : activez *Numéros* ci-dessus pour voir les IDs sur l'image.  \n"
        "**Étape 2** : identifiez anatomiquement chaque point.  \n"
        "**Étape 3** : assignez le nom correct à chaque ID ici.  \n"
        "**Étape 4** : cliquez **Appliquer le mapping**."
    )

    col_r, col_s = st.columns([12, 5])
    with col_r:
        st.markdown("**ID**")
    with col_s:
        st.markdown("**Landmark**")

    mapping_changed = False
    for lm_id in range(1, 30):
        c1, c2 = st.columns([12, 6])
        with c1:
            st.markdown(f"**{lm_id}**")
        with c2:
            sel = st.selectbox(
                f"lm_{lm_id}",
                options=LM_SELECT_OPTIONS,
                index=LM_SELECT_OPTIONS.index(
                    st.session_state.mapping_selections.get(lm_id, LM_SELECT_OPTIONS[0])
                ) if st.session_state.mapping_selections.get(lm_id, LM_SELECT_OPTIONS[0]) in LM_SELECT_OPTIONS else 0,
                key=f"sel_{lm_id}",
                label_visibility="collapsed",
            )
        if sel != st.session_state.mapping_selections.get(lm_id):
            st.session_state.mapping_selections[lm_id] = sel
            mapping_changed = True

    if st.button("✅ Appliquer le mapping", type="primary", use_container_width=True):
        for lm_id in range(1, 30):
            sel = st.session_state.mapping_selections.get(lm_id, LM_SELECT_OPTIONS[0])
            abbr = abbr_from_option(sel)
            st.session_state.lm_mapping[lm_id] = {
                "abbr": abbr,
                "name": name_from_abbr(abbr),
            }
        st.success("Mapping appliqué !")
        st.rerun()

    if st.button("🔄 Reset mapping par défaut", use_container_width=True):
        st.session_state.lm_mapping = {
            i: {"abbr": LM_META[i]["abbr"], "name": LM_META[i]["name"]}
            for i in range(1, 30)
        }
        st.session_state.mapping_selections = {
            i: default_option_for_id(i) for i in range(1, 30)
        }
        st.rerun()

    # Export/Import mapping JSON
    st.divider()
    mapping_json = json.dumps(
        {str(k): v for k, v in st.session_state.lm_mapping.items()},
        ensure_ascii=False, indent=2
    )
    st.download_button(
        "⬇ Exporter mapping JSON",
        data=mapping_json,
        file_name="ceph_mapping.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_mapping = st.file_uploader(
        "⬆ Importer mapping JSON",
        type=["json"],
        key="mapping_upload",
        help="Rechargez un mapping précédemment exporté"
    )
    if uploaded_mapping:
        try:
            raw = json.loads(uploaded_mapping.read())
            new_map = {int(k): v for k, v in raw.items()}
            st.session_state.lm_mapping = new_map
            # Sync selections
            for lm_id, meta in new_map.items():
                abbr = meta.get("abbr","?")
                for opt in LM_SELECT_OPTIONS:
                    if abbr_from_option(opt) == abbr:
                        st.session_state.mapping_selections[lm_id] = opt
                        break
            st.success("Mapping importé !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur import: {e}")


# ── MAIN ─────────────────────────────────────────────────────────
st.title("🦷 Analyse Céphalométrique Multi-Méthodes")
st.caption("Ricketts · Steiner · Downs · Jefferson · Tweed · McNamara · Bjork-Jarabak · Wits · Rakosi · Segner-Hasund · Eastman · ABO · Quick")

st.info(
    "💡 **Premier usage** : activez *Numéros* dans la sidebar, importez une radio, "
    "puis identifiez les points par leur numéro et assignez les noms anatomiques dans le mapping.",
    icon="ℹ️"
)

uploaded = st.file_uploader("Importer une radiographie",
                              type=["png","jpg","jpeg","bmp","tiff"])

if uploaded:
    img_bytes = uploaded.read()
    arr = np.frombuffer(img_bytes, np.uint8)
    img_gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    with st.spinner("🔍 Inférence en cours…"):
        try:
            result = call_predict(img_bytes, uploaded.name)
        except requests.exceptions.ConnectionError:
            st.error("❌ API inaccessible")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ Erreur {e.response.status_code}")
            st.stop()

    landmarks = result["landmarks"]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Landmarks", len(landmarks))
    c2.metric("Inférence", f"{result['inference_ms']} ms")
    c3.metric("TTA", result["tta_passes"])
    c4.metric("Image", f"{result['image_width']}×{result['image_height']} px")

    # Utilise le mapping courant de session_state
    current_mapping = st.session_state.lm_mapping

    canvas_html   = build_canvas_html(
        img_gray, landmarks,
        {"label_mode": init_lbl, "pixel_spacing": ps},
        current_mapping,
    )
    canvas_height = min(int(img_gray.shape[0]*960/img_gray.shape[1]), 840)
    html_b64 = base64.b64encode(canvas_html.encode()).decode()
    st.iframe(f"data:text/html;base64,{html_b64}", height=canvas_height+105)

    # Tableau avec mapping courant
    with st.expander("📐 Coordonnées + mapping courant", expanded=False):
        df = pd.DataFrame([{
            "ID":     lm["id"],
            "Abrév.": current_mapping.get(lm["id"],{}).get("abbr","?"),
            "Nom":    current_mapping.get(lm["id"],{}).get("name","—"),
            "X(px)":  round(lm["x"],1),
            "Y(px)":  round(lm["y"],1),
        } for lm in landmarks])
        st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.info("👆 Importez une radiographie latérale du crâne pour démarrer.")