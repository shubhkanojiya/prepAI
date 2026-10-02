"""
Sample/demo content for development (loaded by `manage.py seed_demo`).

EVERYTHING here is demo data. Papers are labelled "[Demo]" and are NOT
official board papers; their "years" exist only to exercise the historical
frequency analysis. Never present this data as real examination statistics.
"""

BOARDS = [
    # short_name, name, board_type, state, featured, order
    ("CBSE", "Central Board of Secondary Education", "national", "", True, 1),
    ("ICSE", "Council for the Indian School Certificate Examinations", "national", "", True, 2),
    ("MSBSHSE", "Maharashtra State Board of Secondary & Higher Secondary Education", "state", "Maharashtra", True, 3),
    ("GSEB", "Gujarat Secondary and Higher Secondary Education Board", "state", "Gujarat", False, 4),
    ("KSEAB", "Karnataka School Examination and Assessment Board", "state", "Karnataka", False, 5),
    ("TNBSE", "Tamil Nadu State Board of School Examination", "state", "Tamil Nadu", False, 6),
    ("UPMSP", "Uttar Pradesh Madhyamik Shiksha Parishad (UP Board)", "state", "Uttar Pradesh", False, 7),
    ("BSEB", "Bihar School Examination Board", "state", "Bihar", False, 8),
    ("WBBSE", "West Bengal Board of Secondary Education", "state", "West Bengal", False, 9),
]

# board short_name -> class number -> subject name -> {icon, color, popular, chapters: {name: [topics]}}
CURRICULUM = {
    "CBSE": {
        9: {
            "Science": {"icon": "radioactive", "color": "#0f766e", "popular": False, "chapters": {
                "Force and Laws of Motion": ["Balanced and Unbalanced Forces", "Newton's First Law", "Newton's Second Law", "Newton's Third Law"],
                "Motion": ["Distance and Displacement", "Velocity and Acceleration"],
            }},
        },
        10: {
            "Mathematics": {"icon": "calculator", "color": "#2563a8", "popular": True, "chapters": {
                "Real Numbers": ["Fundamental Theorem of Arithmetic", "Irrational Numbers"],
                "Polynomials": ["Zeroes of a Polynomial", "Relationship between Zeroes and Coefficients"],
                "Quadratic Equations": ["Solution by Factorisation", "Quadratic Formula", "Nature of Roots"],
                "Introduction to Trigonometry": ["Trigonometric Ratios", "Trigonometric Identities"],
            }},
            "Science": {"icon": "flask", "color": "#0f766e", "popular": True, "chapters": {
                "Chemical Reactions and Equations": ["Types of Chemical Reactions", "Oxidation and Reduction"],
                "Light – Reflection and Refraction": ["Spherical Mirrors", "Lenses and Power"],
                "Electricity": ["Ohm's Law", "Resistors in Series and Parallel", "Heating Effect of Current"],
                "Life Processes": ["Nutrition", "Respiration"],
            }},
            "English": {"icon": "translate", "color": "#c2410c", "popular": True, "chapters": {
                "Writing Skills": ["Letter Writing", "Analytical Paragraph"],
                "Grammar": ["Tenses", "Reported Speech"],
            }},
        },
        12: {
            "Physics": {"icon": "lightning-charge", "color": "#b45309", "popular": True, "chapters": {
                "Electric Charges and Fields": ["Coulomb's Law", "Electric Field Lines"],
                "Current Electricity": ["Drift Velocity", "Kirchhoff's Rules"],
            }},
            "Accountancy": {"icon": "cash-coin", "color": "#4d7c0f", "popular": False, "chapters": {
                "Accounting for Partnership": ["Profit Sharing Ratio", "Goodwill"],
            }},
        },
    },
    "ICSE": {
        10: {
            "Mathematics": {"icon": "calculator", "color": "#2563a8", "popular": True, "chapters": {
                "Quadratic Equations": ["Solving by Formula"],
                "Trigonometry": ["Identities", "Heights and Distances"],
            }},
            "Physics": {"icon": "lightning-charge", "color": "#b45309", "popular": False, "chapters": {
                "Current Electricity": ["Ohm's Law", "Electrical Power"],
            }},
        },
    },
    "MSBSHSE": {
        10: {
            "Mathematics Part I": {"icon": "calculator", "color": "#2563a8", "popular": False, "chapters": {
                "Quadratic Equations": ["Methods of Solving"],
                "Arithmetic Progression": ["nth Term", "Sum of n Terms"],
            }},
            "Science and Technology Part 1": {"icon": "flask", "color": "#0f766e", "popular": False, "chapters": {
                "Effects of Electric Current": ["Heating Effect", "Magnetic Effect"],
            }},
        },
    },
}

CONCEPTS = {
    ("CBSE", 10, "Mathematics"): ["Factorisation", "Quadratic Formula", "Discriminant", "Trigonometric Ratios",
                                  "Pythagorean Identity", "HCF and LCM", "Irrationality Proofs", "Zeroes of Polynomials"],
    ("CBSE", 10, "Science"): ["Ohm's Law", "Resistance", "Series Combination", "Photosynthesis",
                              "Decomposition Reaction", "Displacement Reaction", "Spherical Mirrors", "Power of a Lens"],
    ("CBSE", 9, "Science"): ["Force", "Motion", "Acceleration", "Inertia", "Action and Reaction"],
}

# Each question: key, (board, class, subject), chapter, topic, type, difficulty, marks, text,
# options [(text, correct)], answer, explanation, concepts, important
Q = "CBSE"
QUESTIONS = [
    # ---- CBSE 10 Mathematics ----
    dict(key="hcf", scope=(Q, 10, "Mathematics"), chapter="Real Numbers", topic="Fundamental Theorem of Arithmetic",
         type="mcq", difficulty="easy", marks=1, text="The HCF of 96 and 404 is:",
         options=[("4", True), ("8", False), ("12", False), ("16", False)],
         explanation="96 = 2⁵ × 3 and 404 = 2² × 101. The common prime factor with the smallest power is 2², so HCF = 4.",
         concepts=["HCF and LCM"]),
    dict(key="irrational", scope=(Q, 10, "Mathematics"), chapter="Real Numbers", topic="Irrational Numbers",
         type="mcq", difficulty="easy", marks=1, text="Which of the following is an irrational number?",
         options=[("√2", True), ("0.25", False), ("22/7", False), ("√16", False)],
         explanation="√16 = 4, 0.25 = 1/4 and 22/7 are rational. √2 cannot be written as p/q, so it is irrational.",
         concepts=["Irrationality Proofs"]),
    dict(key="root5", scope=(Q, 10, "Mathematics"), chapter="Real Numbers", topic="Irrational Numbers",
         type="short", difficulty="medium", marks=3, text="Prove that √5 is irrational.",
         answer="Assume √5 = a/b where a, b are co-prime integers, b ≠ 0.\nThen 5b² = a², so 5 divides a², hence 5 divides a. Write a = 5c.\nThen 5b² = 25c², so b² = 5c² and 5 divides b.\nSo 5 divides both a and b, contradicting that they are co-prime. Hence √5 is irrational.",
         explanation="This is a **proof by contradiction** using the theorem: if a prime p divides a², then p divides a.",
         concepts=["Irrationality Proofs"], important=True),
    dict(key="poly_k", scope=(Q, 10, "Mathematics"), chapter="Polynomials", topic="Zeroes of a Polynomial",
         type="mcq", difficulty="medium", marks=1, text="If one zero of the quadratic polynomial x² + 3x + k is 2, then the value of k is:",
         options=[("−10", True), ("10", False), ("5", False), ("−5", False)],
         explanation="Substitute x = 2: 4 + 6 + k = 0, so k = −10.", concepts=["Zeroes of Polynomials"]),
    dict(key="poly_graph", scope=(Q, 10, "Mathematics"), chapter="Polynomials", topic="Zeroes of a Polynomial",
         type="mcq", difficulty="easy", marks=1,
         text="The graph of a polynomial p(x) intersects the x-axis at exactly three points. The number of zeroes of p(x) is:",
         options=[("3", True), ("2", False), ("1", False), ("0", False)],
         explanation="Each point where the graph meets the x-axis gives a zero, so there are 3 zeroes.",
         concepts=["Zeroes of Polynomials"]),
    dict(key="roots_2x2", scope=(Q, 10, "Mathematics"), chapter="Quadratic Equations", topic="Solution by Factorisation",
         type="mcq", difficulty="easy", marks=1, text="The roots of the equation 2x² − 7x + 3 = 0 are:",
         options=[("3 and 1/2", True), ("−3 and −1/2", False), ("3 and −1/2", False), ("6 and 1", False)],
         explanation="Split the middle term: 2x² − 6x − x + 3 = 2x(x − 3) − 1(x − 3) = (2x − 1)(x − 3). So x = 1/2 or x = 3.",
         concepts=["Factorisation"], important=True),
    dict(key="discriminant", scope=(Q, 10, "Mathematics"), chapter="Quadratic Equations", topic="Nature of Roots",
         type="mcq", difficulty="medium", marks=1, text="The discriminant of the quadratic equation 3x² − 2x + 1/3 = 0 is:",
         options=[("0", True), ("4", False), ("8", False), ("−4", False)],
         explanation="D = b² − 4ac = (−2)² − 4 × 3 × (1/3) = 4 − 4 = 0, so the roots are real and equal.",
         concepts=["Discriminant"]),
    dict(key="larger_root", scope=(Q, 10, "Mathematics"), chapter="Quadratic Equations", topic="Quadratic Formula",
         type="numeric", difficulty="easy", marks=1, text="Find the larger root of x² − 5x + 6 = 0.",
         answer="3", explanation="x² − 5x + 6 = (x − 2)(x − 3), so the roots are 2 and 3. The larger root is 3.",
         concepts=["Factorisation", "Quadratic Formula"]),
    dict(key="distinct_roots", scope=(Q, 10, "Mathematics"), chapter="Quadratic Equations", topic="Nature of Roots",
         type="mcq", difficulty="medium", marks=1, text="Which of the following equations has two distinct real roots?",
         options=[("x² − 3x + 4 = 0", False), ("x² + x + 1 = 0", False), ("x² − 4x + 4 = 0", False), ("2x² − 5x + 2 = 0", True)],
         explanation="Only 2x² − 5x + 2 = 0 has D = 25 − 16 = 9 > 0. The others have D < 0 or D = 0.",
         concepts=["Discriminant"]),
    dict(key="consecutive", scope=(Q, 10, "Mathematics"), chapter="Quadratic Equations", topic="Solution by Factorisation",
         type="short", difficulty="medium", marks=3,
         text="The sum of the squares of two consecutive positive integers is 365. Find the integers.",
         answer="Let the integers be x and x + 1. Then x² + (x + 1)² = 365, so 2x² + 2x − 364 = 0, i.e. x² + x − 182 = 0.\n(x + 14)(x − 13) = 0, and x is positive, so x = 13. The integers are **13 and 14**.",
         explanation="Form the equation from the statement, simplify to standard form and factorise.",
         concepts=["Factorisation"], important=True),
    dict(key="sinA", scope=(Q, 10, "Mathematics"), chapter="Introduction to Trigonometry", topic="Trigonometric Ratios",
         type="mcq", difficulty="easy", marks=1, text="If sin A = 3/5 and A is acute, then cos A is:",
         options=[("4/5", True), ("3/4", False), ("5/4", False), ("5/3", False)],
         explanation="cos A = √(1 − sin²A) = √(1 − 9/25) = √(16/25) = 4/5.",
         concepts=["Trigonometric Ratios", "Pythagorean Identity"]),
    dict(key="sin2cos2", scope=(Q, 10, "Mathematics"), chapter="Introduction to Trigonometry", topic="Trigonometric Identities",
         type="mcq", difficulty="easy", marks=1, text="The value of sin²30° + cos²30° is:",
         options=[("1", True), ("0", False), ("1/2", False), ("3/2", False)],
         explanation="sin²θ + cos²θ = 1 for every angle θ.", concepts=["Pythagorean Identity"]),
    dict(key="tan45", scope=(Q, 10, "Mathematics"), chapter="Introduction to Trigonometry", topic="Trigonometric Ratios",
         type="mcq", difficulty="easy", marks=1, text="tan 45° is equal to:",
         options=[("1", True), ("0", False), ("√3", False), ("1/√3", False)],
         explanation="tan 45° = sin 45° / cos 45° = (1/√2)/(1/√2) = 1.", concepts=["Trigonometric Ratios"]),
    dict(key="sec_tan", scope=(Q, 10, "Mathematics"), chapter="Introduction to Trigonometry", topic="Trigonometric Identities",
         type="fill_blank", difficulty="easy", marks=1, text="sec²θ − tan²θ = ______",
         answer="1|one", explanation="Divide sin²θ + cos²θ = 1 by cos²θ to get tan²θ + 1 = sec²θ.",
         concepts=["Pythagorean Identity"]),
    # ---- CBSE 10 Science ----
    dict(key="decomposition", scope=(Q, 10, "Science"), chapter="Chemical Reactions and Equations", topic="Types of Chemical Reactions",
         type="mcq", difficulty="easy", marks=1, text="Which of the following is a decomposition reaction?",
         options=[("CaCO₃ → CaO + CO₂", True), ("Zn + CuSO₄ → ZnSO₄ + Cu", False), ("NaOH + HCl → NaCl + H₂O", False), ("C + O₂ → CO₂", False)],
         explanation="On heating, calcium carbonate breaks down into two simpler substances — a thermal decomposition reaction.",
         concepts=["Decomposition Reaction"]),
    dict(key="displacement", scope=(Q, 10, "Science"), chapter="Chemical Reactions and Equations", topic="Types of Chemical Reactions",
         type="mcq", difficulty="easy", marks=1, text="The reaction Fe + CuSO₄ → FeSO₄ + Cu is an example of:",
         options=[("Displacement reaction", True), ("Combination reaction", False), ("Decomposition reaction", False), ("Double displacement reaction", False)],
         explanation="Iron is more reactive than copper, so it displaces copper from copper sulphate solution.",
         concepts=["Displacement Reaction"]),
    dict(key="rusting", scope=(Q, 10, "Science"), chapter="Chemical Reactions and Equations", topic="Oxidation and Reduction",
         type="true_false", difficulty="easy", marks=1, text="Rusting of iron is a slow oxidation process.",
         options=[("True", True), ("False", False)],
         explanation="Iron slowly reacts with oxygen and moisture to form hydrated iron(III) oxide (rust)."),
    dict(key="dioptre", scope=(Q, 10, "Science"), chapter="Light – Reflection and Refraction", topic="Lenses and Power",
         type="mcq", difficulty="easy", marks=1, text="The SI unit of power of a lens is:",
         options=[("Dioptre", True), ("Metre", False), ("Watt", False), ("Joule", False)],
         explanation="Power P = 1/f (f in metres). Its unit is the dioptre (D) = m⁻¹.", concepts=["Power of a Lens"]),
    dict(key="concave_c", scope=(Q, 10, "Science"), chapter="Light – Reflection and Refraction", topic="Spherical Mirrors",
         type="mcq", difficulty="medium", marks=1,
         text="A concave mirror forms a real, inverted image of the same size as the object when the object is placed:",
         options=[("At the centre of curvature", True), ("At the focus", False), ("Between the pole and focus", False), ("At infinity", False)],
         explanation="An object at C gives an image at C that is real, inverted and the same size.", concepts=["Spherical Mirrors"]),
    dict(key="ohm", scope=(Q, 10, "Science"), chapter="Electricity", topic="Ohm's Law",
         type="mcq", difficulty="easy", marks=1,
         text="According to Ohm's law, at constant temperature the current through a conductor is:",
         options=[("Directly proportional to the potential difference across it", True), ("Inversely proportional to the potential difference", False), ("Independent of the potential difference", False), ("Proportional to the square of the potential difference", False)],
         explanation="V = IR, so I = V/R: current is directly proportional to V when R is constant.", concepts=["Ohm's Law"]),
    dict(key="current", scope=(Q, 10, "Science"), chapter="Electricity", topic="Ohm's Law",
         type="numeric", difficulty="easy", marks=1,
         text="A 10 Ω resistor is connected across a 5 V battery. What current (in amperes) flows through it?",
         answer="0.5", explanation="I = V/R = 5 V / 10 Ω = 0.5 A.", concepts=["Ohm's Law", "Resistance"], important=True),
    dict(key="series", scope=(Q, 10, "Science"), chapter="Electricity", topic="Resistors in Series and Parallel",
         type="mcq", difficulty="easy", marks=1, text="Resistors of 2 Ω, 3 Ω and 5 Ω are connected in series. The equivalent resistance is:",
         options=[("10 Ω", True), ("0.97 Ω", False), ("30 Ω", False), ("5 Ω", False)],
         explanation="In series, R = R₁ + R₂ + R₃ = 2 + 3 + 5 = 10 Ω.", concepts=["Series Combination", "Resistance"]),
    dict(key="coulomb", scope=(Q, 10, "Science"), chapter="Electricity", topic="Ohm's Law",
         type="mcq", difficulty="easy", marks=1, text="The SI unit of electric charge is:",
         options=[("Coulomb", True), ("Ampere", False), ("Volt", False), ("Ohm", False)],
         explanation="Charge is measured in coulombs (C); 1 C = 1 A × 1 s."),
    dict(key="photosynthesis", scope=(Q, 10, "Science"), chapter="Life Processes", topic="Nutrition",
         type="short", difficulty="medium", marks=3, text="What is photosynthesis? Write its balanced chemical equation.",
         answer="Photosynthesis is the process by which green plants make glucose from carbon dioxide and water using sunlight, in the presence of chlorophyll, releasing oxygen.\n\n6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂ (in sunlight, with chlorophyll)",
         explanation="Key events: absorption of light by chlorophyll, splitting of water, and reduction of CO₂ to carbohydrate.",
         concepts=["Photosynthesis"], important=True),
    dict(key="chloroplast", scope=(Q, 10, "Science"), chapter="Life Processes", topic="Nutrition",
         type="mcq", difficulty="easy", marks=1, text="The site of photosynthesis in a plant cell is the:",
         options=[("Chloroplast", True), ("Mitochondrion", False), ("Nucleus", False), ("Ribosome", False)],
         explanation="Chloroplasts contain chlorophyll, which traps light energy.", concepts=["Photosynthesis"]),
    # ---- CBSE 9 Science ----
    dict(key="newton_laws", scope=(Q, 9, "Science"), chapter="Force and Laws of Motion", topic="Newton's First Law",
         type="long", difficulty="medium", marks=5, text="Explain Newton's laws of motion.",
         answer="**First law (law of inertia):** A body stays at rest or in uniform motion in a straight line unless an unbalanced external force acts on it.\n\n**Second law:** The rate of change of momentum is proportional to the applied force and happens in the direction of the force: F = ma.\n\n**Third law:** To every action there is an equal and opposite reaction, acting on different bodies.",
         explanation="Give one everyday example for each law: a passenger jerking forward when a bus brakes (inertia), pushing a heavier cart needs more force (F = ma), and the recoil of a gun (action–reaction).",
         concepts=["Force", "Motion", "Acceleration", "Inertia", "Action and Reaction"], important=True),
    dict(key="inertia_law", scope=(Q, 9, "Science"), chapter="Force and Laws of Motion", topic="Newton's First Law",
         type="mcq", difficulty="easy", marks=1, text="Newton's first law of motion is also known as the law of:",
         options=[("Inertia", True), ("Momentum", False), ("Action and reaction", False), ("Gravitation", False)],
         explanation="It describes inertia — the tendency of a body to resist a change in its state of motion.", concepts=["Inertia"]),
    dict(key="newton_unit", scope=(Q, 9, "Science"), chapter="Force and Laws of Motion", topic="Newton's Second Law",
         type="mcq", difficulty="easy", marks=1, text="The SI unit of force is:",
         options=[("Newton", True), ("Joule", False), ("Pascal", False), ("Watt", False)],
         explanation="1 N is the force that gives a 1 kg mass an acceleration of 1 m/s².", concepts=["Force"]),
    dict(key="f_ma", scope=(Q, 9, "Science"), chapter="Force and Laws of Motion", topic="Newton's Second Law",
         type="numeric", difficulty="easy", marks=1,
         text="A force gives a 2 kg mass an acceleration of 3 m/s². What is the magnitude of the force in newtons?",
         answer="6", explanation="F = ma = 2 kg × 3 m/s² = 6 N.", concepts=["Force", "Acceleration"]),
    dict(key="recoil", scope=(Q, 9, "Science"), chapter="Force and Laws of Motion", topic="Newton's Third Law",
         type="mcq", difficulty="easy", marks=1, text="The recoil of a gun when a bullet is fired is explained by:",
         options=[("Newton's third law", True), ("Newton's first law", False), ("Newton's law of gravitation", False), ("Ohm's law", False)],
         explanation="The gun pushes the bullet forward (action); the bullet pushes the gun backward (reaction).",
         concepts=["Action and Reaction"]),
]

# Demo "previous-year" papers: (key, scope, year, [(question_key, question_number, marks)])
DEMO_PYP = [
    ("m2019", (Q, 10, "Mathematics"), 2019, [("consecutive", "22", 3), ("sinA", "5", 1), ("root5", "19", 3)]),
    ("m2020", (Q, 10, "Mathematics"), 2020, [("roots_2x2", "4", 1), ("hcf", "1", 1)]),
    ("m2022", (Q, 10, "Mathematics"), 2022, [("consecutive", "24", 3), ("hcf", "2", 1), ("poly_k", "6", 1)]),
    ("m2023", (Q, 10, "Mathematics"), 2023, [("roots_2x2", "3", 1), ("discriminant", "7", 1), ("root5", "20", 3), ("tan45", "9", 1)]),
    ("m2024", (Q, 10, "Mathematics"), 2024, [("consecutive", "23", 3), ("sinA", "8", 1), ("distinct_roots", "10", 1)]),
    ("m2025", (Q, 10, "Mathematics"), 2025, [("discriminant", "6", 1), ("root5", "21", 3), ("sec_tan", "12", 1)]),
    ("s2021", (Q, 10, "Science"), 2021, [("current", "11", 1), ("photosynthesis", "25", 3), ("dioptre", "6", 1)]),
    ("s2023", (Q, 10, "Science"), 2023, [("photosynthesis", "26", 3), ("series", "12", 1), ("ohm", "9", 1)]),
    ("s2024", (Q, 10, "Science"), 2024, [("decomposition", "2", 1), ("current", "13", 1)]),
    ("s2025", (Q, 10, "Science"), 2025, [("photosynthesis", "24", 3), ("current", "10", 1), ("concave_c", "7", 1)]),
    ("p2019", (Q, 9, "Science"), 2019, [("newton_laws", "30", 5)]),
    ("p2021", (Q, 9, "Science"), 2021, [("newton_laws", "29", 5), ("recoil", "8", 1)]),
    ("p2023", (Q, 9, "Science"), 2023, [("newton_laws", "31", 5), ("f_ma", "12", 1)]),
    ("p2025", (Q, 9, "Science"), 2025, [("newton_laws", "30", 5), ("recoil", "9", 1)]),
]

OTHER_PAPERS = [
    # key, scope, paper_type, chapter, title, questions
    ("sample_maths", (Q, 10, "Mathematics"), "sample", None, "[Demo] CBSE Class 10 Mathematics — Sample Paper",
     ["hcf", "poly_k", "roots_2x2", "consecutive", "sinA", "sec_tan"]),
    ("model_science", (Q, 10, "Science"), "model", None, "[Demo] CBSE Class 10 Science — Model Paper",
     ["decomposition", "dioptre", "ohm", "series", "photosynthesis"]),
    ("chapter_quadratic", (Q, 10, "Mathematics"), "chapter_wise", "Quadratic Equations",
     "[Demo] Quadratic Equations — Chapter-wise Practice Paper",
     ["roots_2x2", "discriminant", "larger_root", "distinct_roots", "consecutive"]),
    ("icse_maths", ("ICSE", 10, "Mathematics"), "sample", None, "[Demo] ICSE Class 10 Mathematics — Specimen-style Paper", []),
]

MATERIALS = [
    # scope, chapter, topic, type, title, summary, body, featured
    ((Q, 10, "Mathematics"), "Quadratic Equations", None, "revision", "Quadratic Equations — Revision Notes",
     "Standard form, factorisation, the quadratic formula and the nature of roots on one page.",
     """# Standard form
A quadratic equation is **ax² + bx + c = 0**, where a ≠ 0.

# Methods of solving
1. **Factorisation** — split the middle term so that the product equals ac.
2. **Quadratic formula** — x = (−b ± √(b² − 4ac)) / 2a

# Nature of roots
The discriminant **D = b² − 4ac** decides the roots:
- D > 0 → two distinct real roots
- D = 0 → two equal real roots
- D < 0 → no real roots

# Exam tips
- Always write the equation in standard form first.
- For word problems, define the variable clearly and reject values that don't fit (e.g. negative lengths).""", True),
    ((Q, 10, "Mathematics"), "Introduction to Trigonometry", None, "formula", "Trigonometry Formula Sheet",
     "All ratios, standard angle values and identities you need for Class 10.",
     """# Ratios
- sin θ = opposite / hypotenuse
- cos θ = adjacent / hypotenuse
- tan θ = sin θ / cos θ

# Identities
- sin²θ + cos²θ = 1
- 1 + tan²θ = sec²θ
- 1 + cot²θ = cosec²θ

# Standard values (0°, 30°, 45°, 60°, 90°)
- sin: 0, 1/2, 1/√2, √3/2, 1
- cos: 1, √3/2, 1/√2, 1/2, 0
- tan: 0, 1/√3, 1, √3, not defined""", True),
    ((Q, 10, "Science"), "Electricity", None, "summary", "Electricity — Chapter Summary",
     "Current, potential difference, Ohm's law, resistance and combinations of resistors.",
     """# Key quantities
- **Current (I)** = charge / time, measured in amperes (A)
- **Potential difference (V)** = work done / charge, measured in volts (V)
- **Resistance (R)** measured in ohms (Ω)

# Ohm's law
At constant temperature, **V = IR**.

# Combinations
- Series: R = R₁ + R₂ + R₃
- Parallel: 1/R = 1/R₁ + 1/R₂ + 1/R₃

# Heating effect
H = I²Rt (Joule's law of heating)""", True),
    ((Q, 9, "Science"), "Force and Laws of Motion", None, "concept", "Newton's Laws of Motion — Concept Explanation",
     "Understand inertia, F = ma and action–reaction with everyday examples.",
     """# First law — inertia
Objects keep doing what they are doing unless a net force acts. *Example:* you lurch forward when a bus brakes suddenly.

# Second law — F = ma
The larger the force, the larger the acceleration; heavier objects need more force for the same acceleration.

# Third law — action and reaction
Forces come in pairs acting on **different** bodies. *Example:* a gun recoils when fired.""", False),
    ((Q, 10, "Science"), "Chemical Reactions and Equations", None, "important_questions", "Chemical Reactions — Important Questions",
     "A curated list of commonly practised questions on types of reactions.",
     """1. Why should a magnesium ribbon be cleaned before burning in air?
2. What is a balanced chemical equation? Why should chemical equations be balanced?
3. Give one example each of combination, decomposition, displacement and double displacement reactions.
4. What is rancidity? How can it be prevented?
5. Why is respiration considered an exothermic reaction?""", False),
    ((Q, 10, "Science"), "Life Processes", "Nutrition", "notes", "Nutrition in Plants — Notes",
     "Autotrophic nutrition, photosynthesis and the role of stomata.",
     """# Autotrophic nutrition
Green plants make their own food by **photosynthesis**.

# Equation
6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂ (sunlight, chlorophyll)

# Steps
1. Absorption of light energy by chlorophyll
2. Conversion of light energy to chemical energy and splitting of water
3. Reduction of carbon dioxide to carbohydrates

# Stomata
Tiny pores on leaves for gas exchange; guard cells open and close them.""", False),
    (("ICSE", 10, "Mathematics"), "Quadratic Equations", None, "revision", "ICSE Quadratic Equations — Quick Revision",
     "Formula method and nature of roots for ICSE Class 10.",
     "# Formula\nx = (−b ± √(b² − 4ac)) / 2a\n\n# Nature of roots\nUse the discriminant b² − 4ac.", False),
]

TESTS = [
    # key, title, type, scope, chapter, duration, questions, extra
    ("quad_chapter", "Quadratic Equations — Chapter Test", "chapter", (Q, 10, "Mathematics"), "Quadratic Equations", 15,
     ["roots_2x2", "discriminant", "larger_root", "distinct_roots", "consecutive"], {"is_featured": True}),
    ("elec_chapter", "Electricity — Chapter Test", "chapter", (Q, 10, "Science"), "Electricity", 10,
     ["ohm", "current", "series", "coulomb"], {"is_featured": True}),
    ("trig_practice", "Trigonometry — Practice Test", "practice", (Q, 10, "Mathematics"), "Introduction to Trigonometry", 10,
     ["sinA", "sin2cos2", "tan45", "sec_tan"], {}),
    ("maths_subject", "Class 10 Mathematics — Subject Test", "subject", (Q, 10, "Mathematics"), None, 30,
     ["hcf", "irrational", "poly_k", "poly_graph", "roots_2x2", "discriminant", "distinct_roots", "sinA", "tan45", "sec_tan"], {}),
    ("motion_practice", "Force and Laws of Motion — Practice Test", "practice", (Q, 9, "Science"), "Force and Laws of Motion", 10,
     ["inertia_law", "newton_unit", "f_ma", "recoil"], {}),
    ("board_practice", "CBSE Class 10 — Board Practice Test", "board", (Q, 10, None), None, 20,
     ["hcf", "roots_2x2", "sinA", "decomposition", "ohm", "chloroplast"], {}),
    ("mock_full", "CBSE Class 10 — Full-Length Mock Test (Maths + Science)", "mock", (Q, 10, None), None, 60,
     ["hcf", "irrational", "poly_k", "poly_graph", "roots_2x2", "discriminant", "larger_root", "distinct_roots",
      "sinA", "sin2cos2", "tan45", "sec_tan", "decomposition", "displacement", "rusting", "dioptre", "concave_c",
      "ohm", "current", "series", "coulomb", "chloroplast"], {"is_featured": True, "negative": "0.25"}),
]
