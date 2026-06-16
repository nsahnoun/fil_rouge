import json
import base64
from pathlib import Path

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.security import decode_access_token
from ..models import Analysis, AuditLog, Patient, Radio, Report, User

router = APIRouter()
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _render(name: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    return env.get_template(name).render(**ctx)


async def get_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = int(payload.get("sub"))
            result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.role)))
            return result.scalar_one_or_none()
    return None


LM_META = {
    1:  { "abbr": "A",    "name": "Point A" },
    2:  { "abbr": "ENA",  "name": "Epine nasale antérieure" },
    3:  { "abbr": "B",    "name": "Point B" },
    4:  { "abbr": "Me",   "name": "Menton (Me)" },
    5:  { "abbr": "Na",   "name": "Nasion (Na)" },
    6:  { "abbr": "Or",   "name": "Orbitale" },
    7:  { "abbr": "Pog",  "name": "Pogonion (Pog)" },
    8:  { "abbr": "ENP",  "name": "Epine nasale postérieure" },
    9:  { "abbr": "Pn",   "name": "Pronasale" },    
    10: { "abbr": "R",    "name": "Ramus" },
    11: { "abbr": "S",    "name": "Sellion (S)" },
    12: { "abbr": "Ar",   "name": "Articulare" },
    13: { "abbr": "Co",   "name": "Point condylien" },
    14: { "abbr": "Gn",   "name": "Gnathion" },
    15: { "abbr": "Go",   "name": "Gonion corpus" },
    16: { "abbr": "Po",   "name": "Porion" },
    17: { "abbr": "PM2i", "name": "Point occlusal 5 (2ème prémolaire inf.)" }, 
    18: { "abbr": "Ii",   "name": "Point Incision mandibulaire" },
    19: { "abbr": "Mi_occl",   "name": "Point occlusal 7 (Molaire inf.)" },
    20: { "abbr": "PM2s",  "name": "Pointe occlusale (2ème prémolaire sup.)" },
    21: { "abbr": "Isa",  "name": "Apex incisive maxillaire" },
    24: { "abbr": "Iia",  "name": "Apex incisive mandibulaire" },
    22: { "abbr": "Is",   "name": "Point Incision maxillaire" },
    23: { "abbr": "Ms_occl",  "name": "Point occlusal 8 (Molaire sup.)" },
    25: { "abbr": "Li",   "name": "Lèvre inférieure" },
    26: { "abbr": "Ls",   "name": "Lèvre supérieure" },
    27: { "abbr": "N'",   "name": "Nasion cutané" },
    28: { "abbr": "Pog'", "name": "Pogonion (tissus mous)" },
    29: { "abbr": "Sn",   "name": "Subnasale" },
    30: { "abbr": "Xi",   "name": "Xi (Centre du ramus)" },
    31: { "abbr": "DC",   "name": "DC (Point condylien dérivé)" },
    32: { "abbr": "PT",   "name": "PT (Ptérygoïdien)" }
};


ANATOMICAL_TRACINGS = [
    {"id": "cranial_base", "name": "Base crânienne (Ba-S-N)", "type": "spline", "lms": [10, 11, 5], "color": "#4FC3F7", "width": 1.5, "dash": False},
    {"id": "facial_skeleton", "name": "Squelette facial (N->Or->ANS)", "type": "spline", "lms": [5, 6, 2, 1], "color": "#4FC3F7", "width": 1.5, "dash": False},
    {"id": "palatal_plane", "name": "Plan palatin (PNS->ANS)", "type": "straight", "lms": [8, 2], "color": "#4FC3F7", "width": 1.5, "dash": False},
    {"id": "mandible_body", "name": "Corps mandibulaire", "type": "spline", "lms": [12, 15, 4, 7], "color": "#4FC3F7", "width": 1.5, "dash": False},
    {"id": "ramus", "name": "Ramus (Co->Ar->Go)", "type": "spline", "lms": [13, 12, 15], "color": "#4FC3F7", "width": 1.5, "dash": False},
    {"id": "soft_profile", "name": "Profil tissus mous", "type": "spline", "lms": [27, 9, 29, 26, 25, 28], "color": "#80DEEA", "width": 1.5, "dash": False},
    {"id": "tooth_ui", "name": "Incisive sup. (schéma)", "type": "tooth_ui", "lms": [21, 22], "color": "#81C784", "width": 1.5, "dash": False},
    {"id": "tooth_li", "name": "Incisive inf. (schéma)", "type": "tooth_li", "lms": [24, 18], "color": "#81C784", "width": 1.5, "dash": False},
    {"id": "tooth_u6", "name": "Molaire sup. (schéma)", "type": "tooth_u6", "lms": [20, 23], "color": "#81C784", "width": 1.5, "dash": False},
    {"id": "tooth_l6", "name": "Molaire inf. (schéma)", "type": "tooth_l6", "lms": [17, 19], "color": "#81C784", "width": 1.5, "dash": False},
]

ANALYSES_DEF = {
    "Ricketts": {
        "color": "#4fc3f7",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "NPog", "name": "N-Pog (facial)", "lm1": 5, "lm2": 7, "color": "#FF8A65", "ext": True},
            {"id": "Mand", "name": "Plan mandibulaire", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "PP", "name": "Plan palatin", "lm1": 8, "lm2": 2, "color": "#CE93D8", "ext": True},
            {"id": "APog", "name": "A-Pog (dentaire)", "lm1": 1, "lm2": 7, "color": "#A5D6A7", "ext": False},
            {"id": "Eline", "name": "Ligne E", "lm1": 9, "lm2": 28, "color": "#F48FB1", "ext": False},
            {"id": "GoGn", "name": "Go-Gn (corpus)", "lm1": 15, "lm2": 14, "color": "#B39DDB", "ext": False},
            {"id": "PTV", "name": "PTV (ptérygoïdien)", "lm1": 32, "lm2": 4, "color": "#80DEEA", "ext": True},
            {"id": "XiAx", "name": "Xi-DC", "lm1": 30, "lm2": 31, "color": "#FFD700", "ext": False},
        ],
        "measurements": [
            {"nr": 1, "param": "Axe facial (FHP-NPog)", "fn": "angFH", "a1": 5, "a2": 7, "norm": 90, "sd": 3, "unit": "°",
             "info": "Angle entre le plan de Francfort (FH) et le plan facial N-Pog. Évalue la direction de croissance de la mandibule.",
             "evalLow": "Indique une croissance faciale verticale et/ou une classe squelettique II",
             "evalHigh": "Indique une croissance faciale horizontale (brachyfacial)"},
            {"nr": 2, "param": "FMA (FHP-GoMe)", "fn": "angFH", "a1": 15, "a2": 4, "norm": 22, "sd": 5, "unit": "°",
             "info": "Angle du plan mandibulaire (Go-Me) par rapport à FH. Évalue la divergence faciale verticale.",
             "evalLow": "Tendance à une croissance horizontale (brachyfacial)",
             "evalHigh": "Mandibule en retrait au niveau du menton (type dolichofacial), fréquent en classe II"},
            {"nr": 3, "param": "MP(GoMe)-NPog", "fn": "angVV", "a1": 15, "a2": 14, "b1": 5, "b2": 7, "norm": 68, "sd": 3, "unit": "°",
             "info": "Angle entre le plan mandibulaire (Go-Gn) et le plan facial (N-Pog). Évalue la forme de la mandibule.",
             "evalLow": "Indique un modèle de croissance verticale et une tendance à l'occlusion ouverte, que l'on retrouve chez les patients dolichofaciaux",
             "evalHigh": "Indique un modèle de croissance horizontale"},
            {"nr": 4, "param": "ANSXiPM (Hauteur faciale inf.)", "fn": "ang3", "a1": 2, "a2": 30, "a3": 14, "norm": 47, "sd": 4, "unit": "°",
             "info": "Angle ANS-Xi-PM (protubérance mentonnière). Évalue la hauteur de l'étage inférieur de la face.",
             "evalLow": "Étage inférieur réduit",
             "evalHigh": "Tendance à l'occlusion ouverte"},
            {"nr": 5, "param": "DCXi-XiPM (Arc mandibulaire)", "fn": "ang3", "a1": 31, "a2": 30, "a3": 14, "norm": 26, "sd": 4, "unit": "°",
             "info": "Angle DC-Xi-PM. Évalue la courbure de l'arc mandibulaire.",
             "evalLow": "Arc mandibulaire fermé (tendance à la classe III)",
             "evalHigh": "Arc mandibulaire ouvert (tendance à la classe II)"},
            {"nr": 6, "param": "PP-FHP (Plan palatin)", "fn": "angFH", "a1": 8, "a2": 2, "norm": 0, "sd": 3, "unit": "°",
             "info": "Angle du plan palatin (ENP-ENA) par rapport à FH. Évalue l'inclinaison du palais.",
             "evalLow": "Plan palatin incliné vers l'arrière",
             "evalHigh": "Angulation maxillaire normale"},
            {"nr": 7, "param": "A:NPog (Convexité)", "fn": "ptLine", "a1": 1, "l1": 5, "l2": 7, "norm": 2, "sd": 2, "unit": "mm",
             "info": "Distance du point A au plan facial N-Pog. Évalue la convexité squelettique.",
             "evalLow": "Profil concave",
             "evalHigh": "Classe II squelettique"},
            {"nr": 8, "param": "+1:APog (Incisive sup.)", "fn": "ptLine", "a1": 22, "l1": 1, "l2": 7, "norm": 5, "sd": 3, "unit": "mm",
             "info": "Distance du bord incisif supérieur au plan A-Pog. Évalue la position de l'incisive supérieure.",
             "evalLow": "Incisives supérieures rétrusives",
             "evalHigh": "Incisives supérieures protrusives"},
            {"nr": 9, "param": "-1:APog (Incisive inf.)", "fn": "ptLine", "a1": 18, "l1": 1, "l2": 7, "norm": 2, "sd": 2, "unit": "mm",
             "info": "Distance du bord incisif inférieur au plan A-Pog. Évalue la position de l'incisive inférieure.",
             "evalLow": "Incisives inférieures rétrusives",
             "evalHigh": "Incisives inférieures protrusives"},
            {"nr": 10, "param": "-1-APog (Inclinaison incisive inf.)", "fn": "angFH_custom", "a1": 24, "a2": 18, "b1": 1, "b2": 7, "norm": 22, "sd": 4, "unit": "°",
             "info": "Angle de l'axe de l'incisive inférieure par rapport au plan A-Pog. Évalue l'inclinaison de l'incisive inférieure.",
             "evalLow": "Incisives inférieures retroclinées",
             "evalHigh": "Incisives inférieures proclinées"},
            {"nr": 11, "param": "(+6:PTV) ∥ OP (Molaire sup.-PTV)", "fn": "ptLineV", "a1": 23, "l1": 32, "norm": 21, "sd": 3, "unit": "mm",
             "info": "Distance de la molaire supérieure à la verticale ptérygoïdienne (PTV), mesurée parallèlement au plan occlusal.",
             "evalLow": "L'impaction des 2e et 3e molaires est probable",
             "evalHigh": "Molaire supérieure en avant de la PTV"},
            {"nr": 12, "param": "Angle incisif (interincisif)", "fn": "angVV", "a1": 21, "a2": 22, "b1": 24, "b2": 18, "norm": 131, "sd": 8, "unit": "°",
             "info": "Angle entre l'axe des incisives supérieure et inférieure. Évalue la relation interincisive.",
             "evalLow": "Angle incisif fermé (tendance classe II div 1)",
             "evalHigh": "Angle incisif ouvert (tendance classe II div 2)"},
            {"nr": 13, "param": "Lèvre sup. → Ligne E", "fn": "ptLine", "a1": 26, "l1": 9, "l2": 28, "norm": -4, "sd": 2, "unit": "mm",
             "info": "Distance de la lèvre supérieure à la ligne esthétique (Pn-Pog'). Valeur négative = en arrière de la ligne.",
             "evalLow": "Lèvre supérieure rétrusive",
             "evalHigh": "Lèvre supérieure protrusive"},
            {"nr": 14, "param": "Lèvre inf. → Ligne E", "fn": "ptLine", "a1": 25, "l1": 9, "l2": 28, "norm": -2, "sd": 2, "unit": "mm",
             "info": "Distance de la lèvre inférieure à la ligne esthétique (Pn-Pog'). Valeur négative = en arrière de la ligne.",
             "evalLow": "Lèvre inférieure rétrusive",
             "evalHigh": "Lèvre inférieure protrusive"},
        ],
    },
    "Mahony": {
        "color": "#B39DDB",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "PP", "name": "Plan palatin", "lm1": 8, "lm2": 2, "color": "#CE93D8", "ext": True},
            {"id": "Mand", "name": "Plan mandibulaire", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "NPog", "name": "N-Pog (facial)", "lm1": 5, "lm2": 7, "color": "#FF8A65", "ext": True},
            {"id": "APog", "name": "A-Pog (dentaire)", "lm1": 1, "lm2": 7, "color": "#A5D6A7", "ext": False},
            {"id": "Eline", "name": "Ligne E", "lm1": 9, "lm2": 28, "color": "#F48FB1", "ext": False},
            {"id": "GoGn", "name": "Go-Gn (corpus)", "lm1": 15, "lm2": 14, "color": "#B39DDB", "ext": False},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 2, "unit": "°",
             "info": "Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire.",
             "evalLow": "Rétrognathie maxillaire", "evalHigh": "Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 2, "unit": "°",
             "info": "Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule.",
             "evalLow": "Rétrognathie mandibulaire", "evalNormal": "Mandibule bien positionnée", "evalHigh": "Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°",
             "info": "Différence entre SNA et SNB. Évalue la relation sagittale intermaxillaire.",
             "evalLow": "Classe III squelettique", "evalHigh": "Classe II squelettique"},
            {"nr": 4, "param": "Wits", "fn": "wits", "norm": 0, "sd": 2, "unit": "mm",
             "info": "Distance entre les projections de A et B sur le plan occlusal.",
             "evalLow": "Indique la classe squelettique III", "evalNormal": "Relation sagittale normale", "evalHigh": "Indique la classe squelettique II"},
            {"nr": 5, "param": "-1 to +1", "fn": "angVV", "a1": 21, "a2": 22, "b1": 24, "b2": 18, "norm": 131, "sd": 8, "unit": "°",
             "info": "Angle interincisif entre l'axe des incisives supérieure et inférieure.",
             "evalLow": "Angle incisif fermé", "evalNormal": "Angle incisif normal", "evalHigh": "Angle incisif ouvert"},
            {"nr": 6, "param": "-1:APog", "fn": "ptLine", "a1": 18, "l1": 1, "l2": 7, "norm": 2, "sd": 2, "unit": "mm",
             "info": "Distance de l'incisive inférieure au plan A-Pog.",
             "evalLow": "Incisives inférieures rétrusives", "evalHigh": "Incisives inférieures protrusives"},
            {"nr": 7, "param": "UAFH (N:ANS)", "fn": "dist", "a1": 5, "a2": 2, "norm": 54, "sd": 5, "unit": "mm",
             "info": "Hauteur faciale supérieure de Nasion à Épine Nasale Antérieure.",
             "evalLow": "Hauteur faciale supérieure réduite", "evalNormal": "Hauteur normale de la face supérieure", "evalHigh": "Hauteur faciale supérieure augmentée"},
            {"nr": 8, "param": "LAFH (ANS:Me)", "fn": "dist", "a1": 2, "a2": 4, "norm": 71, "sd": 6, "unit": "mm",
             "info": "Hauteur faciale inférieure de l'Épine Nasale Antérieure au Menton.",
             "evalLow": "Hauteur faciale inférieure réduite", "evalNormal": "Hauteur normale de la face inférieure", "evalHigh": "Hauteur faciale inférieure augmentée"},
            {"nr": 9, "param": "ArGoGn (Angle goniaque)", "fn": "ang3", "a1": 12, "a2": 15, "a3": 14, "norm": 125, "sd": 7, "unit": "°",
             "info": "Angle goniaque formé par Articulare-Gonion-Gnathion. Évalue la divergence mandibulaire.",
             "evalLow": "Tendance à l'occlusion fermée",
             "evalHigh": "Tendance à la croissance verticale pouvant conduire à un profil rétrognathique, fréquent chez les patients dolichofaciaux"},
            {"nr": 10, "param": "UL:E-Plane", "fn": "ptLine", "a1": 26, "l1": 9, "l2": 28, "norm": -4, "sd": 2, "unit": "mm",
             "info": "Distance de la lèvre supérieure à la ligne esthétique.",
             "evalLow": "Lèvre supérieure rétrusive", "evalHigh": "Lèvre supérieure protrusive"},
            {"nr": 11, "param": "LL:E-Plane", "fn": "ptLine", "a1": 25, "l1": 9, "l2": 28, "norm": -2, "sd": 2, "unit": "mm",
             "info": "Distance de la lèvre inférieure à la ligne esthétique.",
             "evalLow": "Lèvre inférieure rétrusive", "evalNormal": "Position normale de la lèvre inférieure", "evalHigh": "Lèvre inférieure protrusive"},
            {"nr": 12, "param": "+1-PP (Inc. sup./plan palatin)", "fn": "angVV", "a1": 21, "a2": 22, "b1": 8, "b2": 2, "norm": 108, "sd": 5, "unit": "°",
             "info": "Angle de l'incisive supérieure par rapport au plan palatin.",
             "evalLow": "Incisive supérieure rétroclinée", "evalNormal": "Inclinaison de l'incisive supérieure par rapport au plan palatin normal", "evalHigh": "Incisive supérieure proclinée"},
            {"nr": 13, "param": "IMPA (-1-GoGn)", "fn": "angVV", "a1": 24, "a2": 18, "b1": 15, "b2": 4, "norm": 90, "sd": 5, "unit": "°",
             "info": "Angle de l'incisive inférieure par rapport au plan mandibulaire (Go-Me).",
             "evalLow": "Incisive inférieure rétroclinée", "evalNormal": "Inclinaison normale de l'incisive inférieure", "evalHigh": "Incisive inférieure proclinée"},
            {"nr": 14, "param": "+1:A ⟂ FHP", "fn": "perpFH", "a1": 22, "ref": 1, "norm": 5, "sd": 1, "unit": "mm",
             "info": "Distance horizontale de l'incisive supérieure à la verticale passant par A (perpendiculaire à FH).",
             "evalLow": "Incisives supérieures rétrusives", "evalHigh": "Incisives supérieures protrusives"},
            {"nr": 15, "param": "MP(GoGn)-PP", "fn": "angVV", "a1": 15, "a2": 14, "b1": 8, "b2": 2, "norm": 20, "sd": 7, "unit": "°",
             "info": "Angle entre le plan mandibulaire (Go-Gn) et le plan palatin.",
             "evalLow": "Modèle de croissance horizontale", "evalHigh": "Suggère un modèle de croissance verticale"},
            {"nr": 16, "param": "Mew sup. ind.", "fn": "dist", "a1": 11, "a2": 8, "norm": 38, "sd": 8, "unit": "mm",
             "info": "Distance de Sella à l'Épine Nasale Postérieure. Indicatrice supérieure de Mew.",
             "evalLow": "Ligne indicatrice supérieure courte", "evalNormal": "Ligne indicatrice supérieure normale", "evalHigh": "Ligne indicatrice supérieure longue"},
            {"nr": 17, "param": "UL:Np ⟂ FHP", "fn": "perpFH", "a1": 26, "ref": 5, "norm": 0, "sd": 5, "unit": "mm",
             "info": "Distance horizontale de la lèvre supérieure à la verticale passant par Nasion.",
             "evalLow": "Lèvre supérieure rétrusive", "evalNormal": "Position normale de la lèvre supérieure", "evalHigh": "Lèvre supérieure protrusive"},
            {"nr": 18, "param": "CC:Np ⟂ FHP", "fn": "perpFH", "a1": 28, "ref": 5, "norm": 0, "sd": 5, "unit": "mm",
             "info": "Distance horizontale du pogonion cutané à la verticale passant par Nasion.",
             "evalLow": "Menton rétrusive", "evalHigh": "Menton protrusive"},
            {"nr": 19, "param": "PP-SNP", "fn": "angVV", "a1": 8, "a2": 2, "b1": 11, "b2": 5, "norm": 8, "sd": 4, "unit": "°",
             "info": "Angle du plan palatin par rapport au plan SN.",
             "evalLow": "Plan palatin incliné vers l'avant", "evalHigh": "Indique l'inclinaison postérieure du maxillaire"},
            {"nr": 20, "param": "MxL (Co:A)", "fn": "dist", "a1": 13, "a2": 1, "norm": 94, "sd": 4, "unit": "mm",
             "info": "Longueur maxillaire effective de Condylion à Point A.",
             "evalLow": "Petit maxillaire", "evalHigh": "Grand maxillaire"},
            {"nr": 21, "param": "MnL (Co:Gn)", "fn": "dist", "a1": 13, "a2": 14, "norm": 120, "sd": 4, "unit": "mm",
             "info": "Longueur mandibulaire effective de Condylion à Gnathion.",
             "evalLow": "Petite mandibule", "evalHigh": "Grande mandibule"},
            {"nr": 22, "param": "PFH (S:Go)", "fn": "dist", "a1": 11, "a2": 15, "norm": 82, "sd": 8, "unit": "mm",
             "info": "Hauteur faciale postérieure de Sella à Gonion.",
             "evalLow": "Hauteur faciale postérieure inférieure à la moyenne", "evalHigh": "Hauteur faciale postérieure supérieure à la moyenne"},
            {"nr": 23, "param": "AFH (N:Me)", "fn": "dist", "a1": 5, "a2": 4, "norm": 121, "sd": 8, "unit": "mm",
             "info": "Hauteur faciale antérieure de Nasion à Menton.",
             "evalLow": "Hauteur faciale antérieure réduite", "evalNormal": "Hauteur moyenne de la face antérieure", "evalHigh": "Hauteur faciale antérieure augmentée"},
            {"nr": 24, "param": "S:N", "fn": "dist", "a1": 11, "a2": 5, "norm": 71, "sd": 3, "unit": "mm",
             "info": "Longueur de la base crânienne antérieure de Sella à Nasion.",
             "evalLow": "Base crânienne antérieure courte", "evalNormal": "Longueur moyenne de la base crânienne antérieure", "evalHigh": "Base crânienne antérieure longue"},
            {"nr": 25, "param": "Y-axe (FHP)", "fn": "angFH", "a1": 11, "a2": 14, "norm": 59, "sd": 4, "unit": "°",
             "info": "Angle de l'axe Y (S-Gn) par rapport au plan de Francfort. Évalue la direction de croissance.",
             "evalLow": "Modèle de croissance horizontale",
             "evalHigh": "Fréquent dans les modèles faciaux de classe II, indique un modèle de croissance verticale de la mandibule"},
            {"nr": 26, "param": "NSAr (Angle sellaire)", "fn": "ang3", "a1": 5, "a2": 11, "a3": 12, "norm": 123, "sd": 5, "unit": "°",
             "info": "Angle sellaire N-S-Ar. La variation modifie la position de la cavité glénoïde.",
             "evalLow": "Cavité glénoïde vers le bas/avant",
             "evalNormal": "Positions normales de la cavité glénoïde et de la mandibule",
             "evalHigh": "Cavité glénoïde vers le haut/arrière"},
            {"nr": 27, "param": "CoGn-SNP", "fn": "angFH_custom", "a1": 13, "a2": 14, "b1": 11, "b2": 5, "norm": 50, "sd": 5, "unit": "°",
             "info": "Angle de l'axe mandibulaire (Co-Gn) par rapport au plan SN.",
             "evalLow": "Modèle de croissance horizontale",
             "evalHigh": "Indique un modèle de croissance verticale et une tendance à l'occlusion ouverte, fréquent chez les patients dolichofaciaux"},
            {"nr": 28, "param": "Jefferson (ANS)", "fn": "perpFH", "a1": 2, "ref": 5, "norm": 0, "sd": 2, "unit": "mm",
             "info": "Distance horizontale de l'Épine Nasale Antérieure à la verticale passant par Nasion.",
             "evalLow": "Classe IIb", "evalHigh": "Classe III/Prognathie maxillaire"},
            {"nr": 29, "param": "Jefferson (Pog)", "fn": "perpFH", "a1": 7, "ref": 5, "norm": 0, "sd": 2, "unit": "mm",
             "info": "Distance horizontale du Pogonion à la verticale passant par Nasion.",
             "evalLow": "Classe IIb", "evalHigh": "Classe III/Prognathie mandibulaire"},
        ],
    },
    "Steiner": {
        "color": "#FFD700",
        "planes": [
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NA", "name": "N-A", "lm1": 5, "lm2": 1, "color": "#80DEEA", "ext": True},
            {"id": "NB", "name": "N-B", "lm1": 5, "lm2": 3, "color": "#FFCC80", "ext": True},
            {"id": "NPog", "name": "N-Pog", "lm1": 5, "lm2": 7, "color": "#FF8A65", "ext": True},
            {"id": "GoGn", "name": "Go-Gn", "lm1": 15, "lm2": 14, "color": "#81C784", "ext": True},
            {"id": "OcPl", "name": "Plan occlusal", "lm1": 23, "lm2": 27, "color": "#CE93D8", "ext": True},
        ],
        "measurements": [
            {"nr":1, "param":"SNA", "fn":"ang3","a1":11,"a2":5,"a3":1,"norm":82,"sd":2,"unit":"°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr":2, "param":"SNB", "fn":"ang3","a1":11,"a2":5,"a3":3,"norm":80,"sd":2,"unit":"°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr":3, "param":"ANB", "fn":"anb","norm":2,"sd":2,"unit":"°",
             "info":"Différence entre SNA et SNB. Évalue la relation sagittale entre le maxillaire et la mandibule.",
             "evalLow":"Classe III squelettique","evalHigh":"Classe II squelettique"},
            {"nr":4, "param":"OP-SNP", "fn":"angVV","a1":23,"a2":27,"b1":11,"b2":5,"norm":14,"sd":2,"unit":"°",
             "info":"Angle entre le plan occlusal et le plan SN. Évalue l'inclinaison du plan d'occlusion.",
             "evalLow":"Indique une croissance horizontale ou un cas de morsure squelettique profonde",
             "evalHigh":"Indique un visage long, une croissance verticale ou un cas d'occlusion squelettique ouverte"},
            {"nr":5, "param":"MP(GoGn)-SNP", "fn":"angVV","a1":15,"a2":14,"b1":11,"b2":5,"norm":32,"sd":3,"unit":"°",
             "info":"Angle antérieur entre le plan mandibulaire (GoGn) et le plan SN. Exprime l'inclinaison de la mandibule par rapport à la base antérieure du crâne.",
             "evalLow":"Indique une inclinaison antérieure de la mandibule ou un modèle squelettique à occlusion fermée",
             "evalHigh":"Indique l'inclinaison postérieure de la mandibule ou le schéma squelettique de l'occlusion ouverte"},
            {"nr":6, "param":"+1-NA", "fn":"angVV","a1":21,"a2":23,"b1":5,"b2":1,"norm":22,"sd":2,"unit":"°",
             "info":"Angle de l'incisive supérieure par rapport à la ligne NA.",
             "evalLow":"Incisive supérieure rétrograde","evalHigh":"Incisive supérieure proclinée"},
            {"nr":7, "param":"+1:NA", "fn":"ptLine","a1":23,"l1":5,"l2":1,"norm":4,"sd":2,"unit":"mm",
             "info":"Distance de l'incisive supérieure à la ligne NA.",
             "evalLow":"Incisives supérieures rétrusives","evalHigh":"Incisives supérieures protrusives"},
            {"nr":8, "param":"-1-NB", "fn":"angVV","a1":22,"a2":24,"b1":5,"b2":3,"norm":25,"sd":2,"unit":"°",
             "info":"Angle de l'incisive inférieure par rapport à la ligne NB.",
             "evalLow":"Incisive inférieure rétrograde","evalHigh":"Incisive inférieure proclinée"},
            {"nr":9, "param":"-1:NB", "fn":"ptLine","a1":24,"l1":5,"l2":3,"norm":4,"sd":5,"unit":"mm",
             "info":"Distance de l'incisive inférieure à la ligne NB.",
             "evalLow":"Incisives inférieures rétrusives","evalHigh":"Incisives inférieures protrusives"},
            {"nr":10,"param":"-1 to +1", "fn":"angVV","a1":21,"a2":23,"b1":22,"b2":24,"norm":131,"sd":8,"unit":"°",
             "info":"Angle entre l'axe des incisives supérieure et inférieure.",
             "evalLow":"Angle incisif fermé","evalHigh":"Angle incisif ouvert"},
            {"nr":11,"param":"Rapport de Holdaway", "fn":"ptLine","a1":7,"l1":5,"l2":3,"norm":0,"sd":2,"unit":"mm",
             "info":"Distance du pogonion à la ligne NB. Évalue l'épaisseur de la symphyse.",
             "evalLow":"Symphyse fine","evalHigh":"Symphyse épaisse"},
        ],
    },
    "Downs": {
        "color": "#81C784",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "NPog", "name": "N-Pog (Facial)", "lm1": 5, "lm2": 7, "color": "#FF8A65", "ext": True},
            {"id": "APog", "name": "A-Pog", "lm1": 1, "lm2": 7, "color": "#A5D6A7", "ext": False},
            {"id": "Mand", "name": "Plan mandibulaire", "lm1": 15, "lm2": 14, "color": "#81C784", "ext": True},
            {"id": "OcPl", "name": "Plan occlusal", "lm1": 23, "lm2": 27, "color": "#CE93D8", "ext": True},
            {"id": "AB", "name": "Plan A-B", "lm1": 1, "lm2": 3, "color": "#80DEEA", "ext": True},
        ],
        "measurements": [
            {"nr":1, "param":"FHP-NPog", "fn":"angFH","a1":5,"a2":7,"norm":88,"sd":4,"unit":"°",
             "info":"Angle facial entre FH et N-Pog.",
             "evalLow":"Mandibule en retrait (dolichofacial), fréquent en classe II","evalHigh":"Prognathie mandibulaire"},
            {"nr":2, "param":"Convexité", "fn":"ptLine","a1":1,"l1":5,"l2":7,"norm":0,"sd":5,"unit":"mm",
             "info":"Distance du point A à la ligne N-Pog.",
             "evalHigh":"Profil convexe","evalLow":"Profil concave"},
            {"nr":3, "param":"Plan A-B", "fn":"angVV","a1":1,"a2":3,"b1":5,"b2":7,"norm":-5,"sd":5,"unit":"°",
             "info":"Angle entre le plan A-B et N-Pog.",
             "evalLow":"Classe III squelettique","evalHigh":"Classe II squelettique"},
            {"nr":4, "param":"FMA (FHP-GoMe)", "fn":"angFH","a1":15,"a2":4,"norm":22,"sd":5,"unit":"°",
             "info":"Angle du plan mandibulaire (Go-Me) par rapport à FH.",
             "evalHigh":"Croissance verticale, tendance occlusion ouverte (dolichofacial)"},
            {"nr":5, "param":"Y-axe (FHP)", "fn":"angFH","a1":11,"a2":14,"norm":59,"sd":4,"unit":"°",
             "info":"Angle de l'axe Y (S-Gn) par rapport à FH.",
             "evalHigh":"Croissance verticale de la mandibule, fréquent en classe II"},
            {"nr":6, "param":"FHP-OP", "fn":"angFH","a1":23,"a2":27,"norm":9,"sd":4,"unit":"°",
             "info":"Angle du plan occlusal par rapport à FH.",
             "evalLow":"Plan occlusal incliné vers l'arrière","evalHigh":"Plan occlusal incliné vers l'avant"},
            {"nr":7, "param":"-1 to +1", "fn":"angVV","a1":21,"a2":23,"b1":22,"b2":24,"norm":131,"sd":8,"unit":"°",
             "info":"Angle interincisif.",
             "evalLow":"Angle incisif fermé","evalHigh":"Angle incisif ouvert"},
            {"nr":8, "param":"IMPA (Downs)", "fn":"angFH_custom","a1":22,"a2":24,"b1":15,"b2":4,"norm":0,"sd":5,"unit":"°",
             "info":"Angle de l'incisive inférieure au plan mandibulaire (Go-Me).",
             "evalLow":"Incisive inférieure rétrograde","evalHigh":"Incisive inférieure proclinée"},
            {"nr":9, "param":"IOPA (Downs)", "fn":"angFH_custom","a1":22,"a2":24,"b1":23,"b2":27,"norm":15,"sd":4,"unit":"°",
             "info":"Angle de l'incisive inférieure au plan occlusal.",
             "evalLow":"Inclinaison anormale","evalHigh":"Inclinaison anormale"},
            {"nr":10,"param":"+1:APog", "fn":"ptLine","a1":23,"l1":1,"l2":7,"norm":5,"sd":3,"unit":"mm",
             "info":"Distance de l'incisive supérieure à la ligne A-Pog.",
             "evalLow":"Incisives supérieures rétrusives","evalHigh":"Incisives supérieures protrusives"},
        ],
    },
    "Jefferson": {
        "color": "#B39DDB",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "NPerpFH", "name": "N ⟂ FH", "lm1": 5, "lm2": 5, "color": "#B39DDB", "ext": True},
        ],
        "measurements": [
            {"nr":1, "param":"Jefferson (ANS)", "fn":"perpFH","a1":2,"ref":5,"norm":0,"sd":2,"unit":"mm",
             "info":"Distance horizontale ANS à la verticale passant par Nasion ⟂ FH.",
             "evalLow":"Classe IIb","evalHigh":"Classe III/Prognathie maxillaire"},
            {"nr":2, "param":"Jefferson (Pog)", "fn":"perpFH","a1":7,"ref":5,"norm":0,"sd":2,"unit":"mm",
             "info":"Distance horizontale Pogonion à la verticale passant par Nasion ⟂ FH.",
             "evalLow":"Classe IIb","evalHigh":"Classe III/Prognathie mandibulaire"},
            {"nr":3, "param":"Me:Jeff. vert.", "fn":"ptLine","a1":4,"l1":6,"l2":16,"norm":0,"sd":2,"unit":"mm",
             "info":"Distance verticale du Menton au plan FH.",
             "evalLow":"Mandibule au-dessus de l'arc vertical de Jefferson. Croissance horizontale.","evalHigh":"Mandibule sous l'arc vertical de Jefferson. Croissance verticale."},
        ],
    },
    "Tweed": {
        "color": "#FF8A65",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "Mand", "name": "Plan mandibulaire", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "LiAx", "name": "Axe inc. inf.", "lm1": 22, "lm2": 24, "color": "#CE93D8", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "FMA (FH:Plan mand.)", "fn": "angFH", "a1": 15, "a2": 4, "norm": 25, "sd": 5, "unit": "°"},
            {"nr": 3, "param": "IMPA (Plan mand.:Li)", "fn": "angVV", "a1": 15, "a2": 4, "b1": 22, "b2": 24, "norm": 90, "sd": 5, "unit": "°"},
        ],
    },
    "McNamara": {
        "color": "#CE93D8",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "NperF", "name": "N perp. à FH", "lm1": 5, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NA", "name": "N-A", "lm1": 5, "lm2": 1, "color": "#80DEEA", "ext": True},
            {"id": "Mand", "name": "Plan mandibulaire", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "Maxillary position (A:perp FH à N)", "fn": "perpFH", "a1": 1, "ref": 5, "norm": 0, "sd": 2, "unit": "mm"},
            {"nr": 3, "param": "Effective maxillary length (Co-A)", "fn": "dist", "a1": None, "a2": 1, "norm": 88, "sd": 4, "unit": "mm"},
            {"nr": 4, "param": "Effective mandib. length (Co-Gn)", "fn": "dist", "a1": None, "a2": 14, "norm": 120, "sd": 5, "unit": "mm"},
        ],
    },
    "Bjork-Jarabak": {
        "color": "#80DEEA",
        "planes": [
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "SAr", "name": "S-Ar", "lm1": 11, "lm2": 12, "color": "#4FC3F7", "ext": False},
            {"id": "ArGo", "name": "Ar-Go", "lm1": 12, "lm2": 15, "color": "#81C784", "ext": False},
            {"id": "GoMe", "name": "Go-Me", "lm1": 15, "lm2": 4, "color": "#A5D6A7", "ext": False},
        ],
        "measurements": [
            {"nr": 1, "param": "NSAr (Angle sellaire)", "fn": "ang3", "a1": 5, "a2": 11, "a3": 12, "norm": 123, "sd": 5, "unit": "°",
             "info": "Angle sellaire formé par l'union de la base crânienne antérieure (NS) avec la base crânienne postérieure (SAr). La variation de l'angle modifie la position de la cavité glénoïde, influençant ainsi la position antéropostérieure de la mandibule.",
             "evalLow": "La cavité glénoïde vers le bas et vers l'avant entraîne une implantation de la mandibule vers l'avant, fréquent chez les patients brachiofaciaux",
             "evalHigh": "La cavité glénoïde vers le haut et vers l'arrière entraîne une implantation distale de la mandibule, fréquente chez les patients dolichofaciaux"},
            {"nr": 3, "param": "Gonial Angle (Ar-Go-Me)", "fn": "ang3", "a1": 12, "a2": 15, "a3": 4, "norm": 130, "sd": 7, "unit": "°"},
            {"nr": 7, "param": "Ant. Cranial Base (S-N)", "fn": "dist", "a1": 11, "a2": 5, "norm": 71, "sd": 3, "unit": "mm"},
        ],
    },
    "Wits": {
        "color": "#FFCC80",
        "planes": [
            {"id": "OcPl", "name": "Plan occlusal", "lm1": 23, "lm2": 27, "color": "#CE93D8", "ext": True},
            {"id": "NA", "name": "N-A", "lm1": 5, "lm2": 1, "color": "#80DEEA", "ext": True},
            {"id": "NB", "name": "N-B", "lm1": 5, "lm2": 3, "color": "#FFCC80", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "Wits AO-BO (plan occlusal)", "fn": "wits", "norm": 0, "sd": 2, "unit": "mm",
             "info":"Distance entre les projections des points A et B sur le plan occlusal. Évalue la dysplasie squelettique sagittale indépendamment de la base du crâne.",
             "evalLow":"Indique la classe squelettique III",
             "evalNormal":"Relation sagittale normale",
             "evalHigh":"Indique la classe squelettique II"},
            {"nr": 2, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 3, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 4, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°"},
        ],
    },
    "Segner-Hasund": {
        "color": "#F48FB1",
        "planes": [
            {"id": "SN", "name": "NSL (S-N)", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NL", "name": "NL (Plan nasal)", "lm1": 8, "lm2": 2, "color": "#CE93D8", "ext": True},
            {"id": "ML", "name": "ML (Plan mand.)", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "Ba", "name": "Ba-N", "lm1": 10, "lm2": 5, "color": "#4FC3F7", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 3.5, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 3.5, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°"},
            {"nr": 4, "param": "NSBa (base crânienne)", "fn": "ang3", "a1": 5, "a2": 11, "a3": 10, "norm": 131, "sd": 5, "unit": "°"},
            {"nr": 5, "param": "NL-NSL (Maxilla:SN)", "fn": "angVV", "a1": 8, "a2": 2, "b1": 11, "b2": 5, "norm": 8, "sd": 3, "unit": "°"},
            {"nr": 6, "param": "ML-NSL (Mand.:SN)", "fn": "angVV", "a1": 15, "a2": 4, "b1": 11, "b2": 5, "norm": 32, "sd": 5, "unit": "°"},
            {"nr": 7, "param": "NL-ML (MMPA)", "fn": "angVV", "a1": 8, "a2": 2, "b1": 15, "b2": 4, "norm": 24, "sd": 5, "unit": "°"},
            {"nr": 8, "param": "NSGn (Y-Axis:SN)", "fn": "angFH_custom", "a1": 11, "a2": 14, "b1": 11, "b2": 5, "norm": 66, "sd": 3, "unit": "°"},
            {"nr": 9, "param": "Ui:NL (inc. sup.:PP)", "fn": "angVV", "a1": 21, "a2": 23, "b1": 8, "b2": 2, "norm": 110, "sd": 6, "unit": "°"},
            {"nr": 10, "param": "Li:ML (inc. inf.:MP)", "fn": "angVV", "a1": 22, "a2": 24, "b1": 15, "b2": 4, "norm": 94, "sd": 6, "unit": "°"},
            {"nr": 11, "param": "Interincisal Angle", "fn": "angVV", "a1": 21, "a2": 23, "b1": 22, "b2": 24, "norm": 132, "sd": 8, "unit": "°"},
        ],
    },
    "Rakosi": {
        "color": "#A5D6A7",
        "planes": [
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NL", "name": "Plan nasal", "lm1": 8, "lm2": 2, "color": "#CE93D8", "ext": True},
            {"id": "ML", "name": "Plan mand.", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "ArGo", "name": "Ar-Go", "lm1": 12, "lm2": 15, "color": "#4FC3F7", "ext": False},
            {"id": "GoGn", "name": "Go-Gn", "lm1": 15, "lm2": 14, "color": "#A5D6A7", "ext": False},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°"},
            {"nr": 4, "param": "GoGn to SN", "fn": "angVV", "a1": 15, "a2": 14, "b1": 11, "b2": 5, "norm": 32, "sd": 5, "unit": "°",
             "info":"Angle antérieur entre le plan mandibulaire (GoGn) et le plan SN. Exprime l'inclinaison de la mandibule par rapport à la base antérieure du crâne.",
             "evalLow":"Indique une inclinaison antérieure de la mandibule ou un modèle squelettique à occlusion fermée",
             "evalHigh":"Indique l'inclinaison postérieure de la mandibule ou le schéma squelettique de l'occlusion ouverte"},
            {"nr": 5, "param": "NL to SN", "fn": "angVV", "a1": 8, "a2": 2, "b1": 11, "b2": 5, "norm": 7, "sd": 3, "unit": "°"},
            {"nr": 6, "param": "NL to ML (MMPA)", "fn": "angVV", "a1": 8, "a2": 2, "b1": 15, "b2": 4, "norm": 25, "sd": 5, "unit": "°"},
            {"nr": 7, "param": "Gonial angle (Ar-Go-Gn)", "fn": "ang3", "a1": 12, "a2": 15, "a3": 14, "norm": 128, "sd": 7, "unit": "°"},
            {"nr": 8, "param": "Ramus Inclination", "fn": "angFH", "a1": 12, "a2": 15, "norm": 76, "sd": 4, "unit": "°"},
            {"nr": 9, "param": "S-Ar distance", "fn": "dist", "a1": 11, "a2": 12, "norm": 32, "sd": 3, "unit": "mm"},
            {"nr": 10, "param": "Ar-Go distance", "fn": "dist", "a1": 12, "a2": 15, "norm": 44, "sd": 4, "unit": "mm"},
            {"nr": 11, "param": "Go-Gn distance", "fn": "dist", "a1": 15, "a2": 14, "norm": 71, "sd": 5, "unit": "mm"},
            {"nr": 12, "param": "Ui to NL (angle)", "fn": "angVV", "a1": 21, "a2": 23, "b1": 8, "b2": 2, "norm": 110, "sd": 6, "unit": "°"},
            {"nr": 13, "param": "Li to ML (IMPA)", "fn": "angVV", "a1": 22, "a2": 24, "b1": 15, "b2": 4, "norm": 94, "sd": 7, "unit": "°"},
            {"nr": 14, "param": "Interincisal Angle", "fn": "angVV", "a1": 21, "a2": 23, "b1": 22, "b2": 24, "norm": 130, "sd": 8, "unit": "°"},
        ],
    },
    "Eastman": {
        "color": "#FFAB91",
        "planes": [
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NL", "name": "Plan nasal (NL)", "lm1": 8, "lm2": 2, "color": "#CE93D8", "ext": True},
            {"id": "ML", "name": "Plan mand. (ML)", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "NA", "name": "N-A", "lm1": 5, "lm2": 1, "color": "#80DEEA", "ext": True},
            {"id": "NB", "name": "N-B", "lm1": 5, "lm2": 3, "color": "#FFCC80", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 81, "sd": 3, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 78, "sd": 3, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB (Eastman corr.)", "fn": "anb", "norm": 3, "sd": 2, "unit": "°"},
            {"nr": 4, "param": "MMPA (NL-ML)", "fn": "angVV", "a1": 8, "a2": 2, "b1": 15, "b2": 4, "norm": 27, "sd": 5, "unit": "°"},
            {"nr": 5, "param": "Ui to MaxPlane (NL)", "fn": "angVV", "a1": 21, "a2": 23, "b1": 8, "b2": 2, "norm": 109, "sd": 6, "unit": "°"},
            {"nr": 6, "param": "Li to MandPlane (ML)", "fn": "angVV", "a1": 22, "a2": 24, "b1": 15, "b2": 4, "norm": 93, "sd": 6, "unit": "°"},
            {"nr": 7, "param": "Interincisal Angle", "fn": "angVV", "a1": 21, "a2": 23, "b1": 22, "b2": 24, "norm": 133, "sd": 8, "unit": "°"},
            {"nr": 8, "param": "Ui to NA (mm)", "fn": "ptLine", "a1": 23, "l1": 5, "l2": 1, "norm": 4, "sd": 2, "unit": "mm"},
            {"nr": 9, "param": "Li to NB (mm)", "fn": "ptLine", "a1": 24, "l1": 5, "l2": 3, "norm": 4, "sd": 2, "unit": "mm"},
            {"nr": 10, "param": "Z-Angle (FH:Ul-Pog')", "fn": "angFH", "a1": 26, "a2": 28, "norm": 75, "sd": 5, "unit": "°"},
        ],
    },
    "ABO": {
        "color": "#B39DDB",
        "planes": [
            {"id": "FH", "name": "FH (Francfort)", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NA", "name": "N-A", "lm1": 5, "lm2": 1, "color": "#80DEEA", "ext": True},
            {"id": "NB", "name": "N-B", "lm1": 5, "lm2": 3, "color": "#FFCC80", "ext": True},
            {"id": "Mand", "name": "Plan mand.", "lm1": 15, "lm2": 4, "color": "#81C784", "ext": True},
            {"id": "OcPl", "name": "Plan occlusal", "lm1": 23, "lm2": 27, "color": "#CE93D8", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°"},
            {"nr": 4, "param": "FMA (FH:GoMe)", "fn": "angFH", "a1": 15, "a2": 4, "norm": 25, "sd": 5, "unit": "°"},
            {"nr": 5, "param": "IMPA (GoMe:Li)", "fn": "angVV", "a1": 15, "a2": 4, "b1": 22, "b2": 24, "norm": 95, "sd": 5, "unit": "°"},
            {"nr": 6, "param": "FMIA (FH:Li)", "fn": "angFH", "a1": 22, "a2": 24, "norm": 65, "sd": 7, "unit": "°"},
            {"nr": 7, "param": "GoGn to SN", "fn": "angVV", "a1": 15, "a2": 14, "b1": 11, "b2": 5, "norm": 32, "sd": 5, "unit": "°",
             "info":"Angle antérieur entre le plan mandibulaire (GoGn) et le plan SN. Exprime l'inclinaison de la mandibule par rapport à la base antérieure du crâne.",
             "evalLow":"Indique une inclinaison antérieure de la mandibule ou un modèle squelettique à occlusion fermée",
             "evalHigh":"Indique l'inclinaison postérieure de la mandibule ou le schéma squelettique de l'occlusion ouverte"},
            {"nr": 8, "param": "Occlusal plane to SN", "fn": "angVV", "a1": 23, "a2": 27, "b1": 11, "b2": 5, "norm": 14, "sd": 4, "unit": "°"},
            {"nr": 9, "param": "Ui to NA (mm)", "fn": "ptLine", "a1": 23, "l1": 5, "l2": 1, "norm": 4, "sd": 2, "unit": "mm"},
            {"nr": 10, "param": "Li to NB (mm)", "fn": "ptLine", "a1": 24, "l1": 5, "l2": 3, "norm": 4, "sd": 2, "unit": "mm"},
            {"nr": 11, "param": "Ui to NA (angle)", "fn": "angVV", "a1": 21, "a2": 23, "b1": 5, "b2": 1, "norm": 22, "sd": 5, "unit": "°"},
            {"nr": 12, "param": "Interincisal Angle", "fn": "angVV", "a1": 21, "a2": 23, "b1": 22, "b2": 24, "norm": 130, "sd": 6, "unit": "°"},
            {"nr": 13, "param": "Overjet", "fn": "overjet", "norm": 2, "sd": 1, "unit": "mm"},
            {"nr": 14, "param": "Overbite", "fn": "overbite", "norm": 2, "sd": 1, "unit": "mm"},
        ],
    },
    "Quick": {
        "color": "#E0E0E0",
        "planes": [
            {"id": "FH", "name": "FH", "lm1": 6, "lm2": 16, "color": "#FF6B6B", "ext": True},
            {"id": "SN", "name": "S-N", "lm1": 11, "lm2": 5, "color": "#FFD700", "ext": True},
            {"id": "NB", "name": "N-B", "lm1": 5, "lm2": 3, "color": "#FFCC80", "ext": True},
        ],
        "measurements": [
            {"nr": 1, "param": "SNA", "fn": "ang3", "a1": 11, "a2": 5, "a3": 1, "norm": 82, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:A. Évalue la position antéro-postérieure du maxillaire par rapport à la base du crâne.",
             "evalLow":"Rétrognathie maxillaire","evalHigh":"Prognathie maxillaire"},
            {"nr": 2, "param": "SNB", "fn": "ang3", "a1": 11, "a2": 5, "a3": 3, "norm": 80, "sd": 2, "unit": "°",
             "info":"Angle Sella:Nasion:B. Évalue la position antéro-postérieure de la mandibule par rapport à la base du crâne.",
             "evalLow":"Rétrognathie mandibulaire","evalNormal":"Mandibule bien positionnée","evalHigh":"Prognathie mandibulaire"},
            {"nr": 3, "param": "ANB", "fn": "anb", "norm": 2, "sd": 2, "unit": "°"},
            {"nr": 4, "param": "FMA", "fn": "angFH", "a1": 15, "a2": 4, "norm": 25, "sd": 5, "unit": "°"},
            {"nr": 5, "param": "IMPA", "fn": "angVV", "a1": 15, "a2": 4, "b1": 22, "b2": 24, "norm": 95, "sd": 5, "unit": "°"},
            {"nr": 6, "param": "Overjet", "fn": "overjet", "norm": 2, "sd": 1, "unit": "mm"},
            {"nr": 7, "param": "Overbite", "fn": "overbite", "norm": 2, "sd": 1, "unit": "mm"},
        ],
    },
}


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return _render("auth/login.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    stats = {"patients": 0, "analyses": 0, "validated_analyses": 0, "reports": 0}
    try:
        stats["patients"] = (await db.execute(select(func.count(Patient.id)))).scalar() or 0
        stats["analyses"] = (await db.execute(select(func.count(Analysis.id)))).scalar() or 0
        stats["validated_analyses"] = (await db.execute(select(func.count(Analysis.id)).where(Analysis.status == "validated"))).scalar() or 0
        stats["reports"] = (await db.execute(select(func.count(Report.id)))).scalar() or 0
    except Exception:
        pass
    recent_activity = []
    try:
        audit_result = await db.execute(
            select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(10)
        )
        for log in audit_result.scalars().all():
            uname = f"{log.user.first_name} {log.user.last_name}" if log.user else "—"
            recent_activity.append({
                "id": log.id, "user_name": uname, "action": log.action,
                "resource_type": log.resource_type, "resource_id": log.resource_id,
                "created_at": str(log.created_at)[:19] if log.created_at else "",
            })
    except Exception:
        pass
    if not recent_activity:
        recent_activity.append({"id": 0, "user_name": "", "action": "Aucune activité récente", "resource_type": "", "resource_id": "", "created_at": ""})
    return _render("dashboard/index.html", current_user=user, stats=stats, recent_activity=recent_activity, show_sidebar=True)


@router.get("/patients", response_class=HTMLResponse)
async def patients_page(request: Request, db: AsyncSession = Depends(get_db), offset: int = Query(0), limit: int = Query(50)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    total = (await db.execute(select(func.count(Patient.id)))).scalar() or 0
    result = await db.execute(select(Patient).order_by(Patient.created_at.desc()).offset(offset).limit(limit + 1))
    patients = result.scalars().all()
    has_more = len(patients) > limit
    if has_more:
        patients = patients[:limit]
    return _render("patients/list.html", current_user=user, patients=[
        {"id": p.id, "first_name": p.first_name, "last_name": p.last_name, "birth_date": p.birth_date,
         "email": p.email}
        for p in patients
    ], show_sidebar=True, page_offset=offset, page_limit=limit, has_more=has_more, total=total)


@router.get("/patients/new", response_class=HTMLResponse)
async def patient_create_page(request: Request, db: AsyncSession = Depends(get_db), edit: int | None = Query(None)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    patient_data = {}
    title = "Nouveau patient"
    if edit:
        result = await db.execute(select(Patient).where(Patient.id == edit))
        p = result.scalar_one_or_none()
        if p:
            title = "Modifier le patient"
            patient_data = {
                "id": p.id, "first_name": p.first_name, "last_name": p.last_name,
                "birth_date": p.birth_date, "gender": p.gender, "email": p.email,
                "phone": p.phone, "address": p.address, "medical_id": p.medical_id,
                "referring_doctor": p.referring_doctor, "medical_history": p.medical_history,
                "allergies": p.allergies, "medications": p.medications, "insurance_info": p.insurance_info,
            }
    return _render("patients/form.html", title=title, patient=patient_data, current_user=user, show_sidebar=True)


@router.get("/patients/{patient_id}", response_class=HTMLResponse)
async def patient_detail_page(patient_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Patient introuvable")
    age = None
    if p.birth_date:
        from datetime import date
        today = date.today()
        try:
            bd = p.birth_date if hasattr(p.birth_date, 'year') else p.birth_date
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        except Exception:
            pass
    return _render("patients/detail.html", current_user=user, patient={
        "id": p.id, "first_name": p.first_name, "last_name": p.last_name,
        "birth_date": p.birth_date, "gender": p.gender, "email": p.email,
        "phone": p.phone, "medical_id": p.medical_id, "age": age,
    }, show_sidebar=True)


@router.get("/analyses/{analysis_id}", response_class=HTMLResponse)
async def analysis_canvas_page(analysis_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id).options(selectinload(Analysis.radio)))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analyse introuvable")
    radio = analysis.radio
    img_gray = None
    if Path(radio.file_path).exists():
        import cv2
        img_gray = cv2.imread(radio.file_path, cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        raise HTTPException(404, "Image radio introuvable")
    import cv2
    _, buf = cv2.imencode(".png", cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB))
    img_b64 = base64.b64encode(buf.tobytes()).decode()
    landmarks = json.loads(analysis.landmarks) if analysis.landmarks else []
    pixel_spacing = radio.pixel_spacing or 0.1
    injected = (
        'const IMG_B64        = "' + img_b64 + '";\n'
        'const INIT_LMS       = ' + json.dumps(landmarks) + ';\n'
        'const ABBREV         = ' + json.dumps({k: v["abbr"] for k, v in LM_META.items()}) + ';\n'
        'const LM_NAMES       = ' + json.dumps({k: v["name"] for k, v in LM_META.items()}) + ';\n'
        'const ANATOMICAL     = ' + json.dumps(ANATOMICAL_TRACINGS) + ';\n'
        'const ANALYSES       = ' + json.dumps(ANALYSES_DEF) + ';\n'
        'const INIT_LBL_MODE  = "abbrev";\n'
        'const INIT_PS        = ' + str(pixel_spacing) + ';\n'
        'const ANALYSIS_ID    = ' + str(analysis.id) + ';\n'
    )
    return _render("analyses/canvas.html", injected_data=injected)


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user or user.role.name != "admin":
        return RedirectResponse(url="/dashboard")
    result = await db.execute(select(User).options(selectinload(User.role)))
    users = result.scalars().all()
    return _render("admin/users.html", current_user=user, users=[
        {"id": u.id, "email": u.email, "first_name": u.first_name, "last_name": u.last_name,
         "role": u.role.name, "is_active": u.is_active, "last_login": u.last_login}
        for u in users
    ], show_sidebar=True)


@router.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user or user.role.name != "admin":
        return RedirectResponse(url="/dashboard")
    return _render("admin/audit.html", current_user=user, show_sidebar=True)


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page():
    return _render("auth/register.html")


@router.get("/auth/logout")
async def logout_page():
    r = RedirectResponse(url="/login")
    r.delete_cookie("access_token")
    return r


@router.get("/analyses", response_class=HTMLResponse)
async def analyses_page(request: Request, db: AsyncSession = Depends(get_db), offset: int = Query(0), limit: int = Query(50)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    total = (await db.execute(select(func.count(Analysis.id)))).scalar() or 0
    result = await db.execute(
        select(Analysis).options(selectinload(Analysis.radio)).order_by(Analysis.created_at.desc()).offset(offset).limit(limit + 1)
    )
    analyses = result.scalars().all()
    has_more = len(analyses) > limit
    if has_more:
        analyses = analyses[:limit]
    analyses_data = []
    for a in analyses:
        pid = a.radio.patient_id if a.radio else None
        pname = ""
        if pid:
            pr = await db.execute(select(Patient).where(Patient.id == pid))
            p = pr.scalar_one_or_none()
            pname = f"{p.first_name} {p.last_name}" if p else ""
        analyses_data.append({
            "id": a.id, "patient_id": pid, "patient_name": pname,
            "status": a.status, "version": a.version, "inference_ms": a.inference_ms or 0,
            "created_at": str(a.created_at) if a.created_at else "",
        })
    return _render("analyses/list.html", current_user=user, analyses=analyses_data, show_sidebar=True,
                   page_offset=offset, page_limit=limit, has_more=has_more, total=total)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: AsyncSession = Depends(get_db), offset: int = Query(0), limit: int = Query(50)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    total = (await db.execute(select(func.count(Report.id)))).scalar() or 0
    result = await db.execute(select(Report).order_by(Report.created_at.desc()).offset(offset).limit(limit + 1))
    reports = result.scalars().all()
    has_more = len(reports) > limit
    if has_more:
        reports = reports[:limit]
    reports_data = []
    for r in reports:
        pname = ""
        pr = await db.execute(select(Patient).where(Patient.id == r.patient_id))
        p = pr.scalar_one_or_none()
        pname = f"{p.first_name} {p.last_name}" if p else ""
        reports_data.append({
            "id": r.id, "patient_id": r.patient_id, "patient_name": pname,
            "report_type": r.report_type, "signed_by": r.signed_by,
            "status": "signé" if r.signed_by else "brouillon",
            "created_at": str(r.created_at) if r.created_at else "",
        })
    return _render("reports/list.html", current_user=user, reports=reports_data, show_sidebar=True,
                   page_offset=offset, page_limit=limit, has_more=has_more, total=total)


@router.get("/reports/{report_id}", response_class=HTMLResponse)
async def report_detail_page(report_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Rapport introuvable")
    pname = ""
    pr = await db.execute(select(Patient).where(Patient.id == r.patient_id))
    p = pr.scalar_one_or_none()
    pname = f"{p.first_name} {p.last_name}" if p else ""
    content = r.content_html or ""
    has_file = bool(r.file_path and Path(r.file_path).exists())
    return _render("reports/detail.html", current_user=user, report={
        "id": r.id, "patient_id": r.patient_id, "patient_name": pname,
        "report_type": r.report_type, "signed_by": r.signed_by,
        "status": "signé" if r.signed_by else "brouillon",
        "created_at": str(r.created_at) if r.created_at else "",
        "content_html": content,
        "has_file": has_file,
    }, show_sidebar=True)


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user(request, db)
    if not user or user.role.name != "admin":
        return RedirectResponse(url="/dashboard")
    from ..core.config import settings as app_settings
    from ..models import ClinicSetting
    result = await db.execute(select(ClinicSetting))
    overrides = {s.setting_key: s.setting_value for s in result.scalars().all()}
    return _render("admin/settings.html", current_user=user, settings={
        "clinic_name": overrides.get("clinic_name", app_settings.clinic_name),
        "clinic_city": overrides.get("clinic_city", app_settings.clinic_city),
        "clinic_address": overrides.get("clinic_address", ""),
        "ceph_api_url": overrides.get("ceph_api_url", app_settings.ceph_api_url),
    }, show_sidebar=True)


@router.get("/admin", response_class=RedirectResponse)
async def admin_home():
    return RedirectResponse(url="/admin/users")

@router.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/dashboard")
