"""Hand-entered public-domain melodies (well-known tunes judges will recognize).

Durations are in beats. These are transcribed by ear/memory for the demo, so a few
notes may differ from a particular edition; matching is fuzzy, so that is fine.
All works are traditional or by composers who died long before 1929.
"""

FAMOUS = [
    ("Twinkle Twinkle Little Star", "Traditional (French melody)",
     "C4:1 C4 G4 G4 A4 A4 G4:2 F4:1 F4 E4 E4 D4 D4 C4:2 "
     "G4:1 G4 F4 F4 E4 E4 D4:2 G4:1 G4 F4 F4 E4 E4 D4:2 "
     "C4:1 C4 G4 G4 A4 A4 G4:2 F4:1 F4 E4 E4 D4 D4 C4:2"),
    ("Ode to Joy (Symphony No. 9)", "Ludwig van Beethoven",
     "E4:1 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:1.5 D4:0.5 D4:2 "
     "E4:1 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:0.5 C4:2 "
     "D4:1 D4 E4 C4 D4 E4:0.5 F4 E4:1 C4 D4 E4:0.5 F4 E4:1 D4 C4 D4 G3:2 "
     "E4:1 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:0.5 C4:2"),
    ("Mary Had a Little Lamb", "Traditional",
     "E4:1 D4 C4 D4 E4 E4 E4:2 D4:1 D4 D4:2 E4:1 G4 G4:2 "
     "E4:1 D4 C4 D4 E4 E4 E4 E4 D4 D4 E4 D4 C4:4"),
    ("Happy Birthday to You", "Mildred & Patty Hill (public domain)",
     "G4:0.75 G4:0.25 A4:1 G4 C5 B4:2 G4:0.75 G4:0.25 A4:1 G4 D5 C5:2 "
     "G4:0.75 G4:0.25 G5:1 E5 C5 B4 A4 F5:0.75 F5:0.25 E5:1 C5 D5 C5:2"),
    ("Jingle Bells", "James Lord Pierpont",
     "E4:1 E4 E4:2 E4:1 E4 E4:2 E4:1 G4 C4:1.5 D4:0.5 E4:4 "
     "F4:1 F4 F4:1.5 F4:0.5 F4:1 E4 E4 E4:0.5 E4:0.5 E4:1 D4 D4 E4 D4:2 G4:2 "
     "E4:1 E4 E4:2 E4:1 E4 E4:2 E4:1 G4 C4:1.5 D4:0.5 E4:4 "
     "F4:1 F4 F4:1.5 F4:0.5 F4:1 E4 E4 E4:0.5 E4:0.5 G4:1 G4 F4 D4 C4:4"),
    ("Frère Jacques", "Traditional (French)",
     "C4:1 D4 E4 C4 C4 D4 E4 C4 E4 F4 G4:2 E4:1 F4 G4:2 "
     "G4:0.5 A4 G4 F4 E4:1 C4 G4:0.5 A4 G4 F4 E4:1 C4 C4 G3 C4:2 C4:1 G3 C4:2"),
    ("Für Elise", "Ludwig van Beethoven",
     "E5:0.5 D#5 E5 D#5 E5 B4 D5 C5 A4:1 r:0.5 C4:0.5 E4 A4 B4:1 r:0.5 E4:0.5 G#4 B4 C5:1 r:0.5 "
     "E4:0.5 E5 D#5 E5 D#5 E5 B4 D5 C5 A4:1 r:0.5 C4:0.5 E4 A4 B4:1 r:0.5 E4:0.5 C5 B4 A4:2"),
    ("Amazing Grace", "Traditional (lyrics John Newton)",
     "D4:1 G4:2 B4:0.5 G4:0.5 B4:2 A4:1 G4:2 E4:1 D4:2 D4:1 G4:2 B4:0.5 G4:0.5 B4:2 A4:1 D5:3 "
     "r:2 B4:1 D5:1.5 B4:0.5 D5:0.5 B4:0.5 G4:2 D4:1 E4:1.5 G4:0.5 G4:0.5 E4:0.5 D4:2 D4:1 "
     "G4:2 B4:0.5 G4:0.5 B4:2 A4:1 G4:3"),
    ("Greensleeves", "Traditional (English)",
     "A4:1 C5:2 D5:1 E5:1.5 F5:0.5 E5:1 D5:2 B4:1 G4:1.5 A4:0.5 B4:1 C5:2 A4:1 "
     "A4:1.5 G#4:0.5 A4:1 B4:2 G#4:1 E4:2 A4:1 C5:2 D5:1 E5:1.5 F5:0.5 E5:1 D5:2 B4:1 "
     "G4:1.5 A4:0.5 B4:1 C5:1.5 B4:0.5 A4:1 G#4:1.5 F#4:0.5 G#4:1 A4:3"),
    ("Row, Row, Row Your Boat", "Traditional",
     "C4:1.5 C4:1.5 C4:1 D4:0.5 E4:1.5 E4:1 D4:0.5 E4:1 F4:0.5 G4:3 "
     "C5:0.5 C5 C5 G4 G4 G4 E4 E4 E4 C4 C4 C4 G4:1 F4:0.5 E4:1 D4:0.5 C4:3"),
    ("London Bridge Is Falling Down", "Traditional",
     "G4:1.5 A4:0.5 G4:1 F4 E4 F4 G4:2 D4:1 E4 F4:2 E4:1 F4 G4:2 "
     "G4:1.5 A4:0.5 G4:1 F4 E4 F4 G4:2 D4:2 G4:2 E4:1 C4:3"),
    ("When the Saints Go Marching In", "Traditional (spiritual)",
     "C4:1 E4 F4 G4:5 C4:1 E4 F4 G4:5 C4:1 E4 F4 G4:2 E4:2 C4:2 E4:2 D4:4 "
     "E4:1 E4 D4 C4:3 C4:1 E4:2 G4:2 G4:1 F4:3 E4:1 F4 G4:2 E4:2 C4:2 D4:2 C4:4"),
    ("Old MacDonald Had a Farm", "Traditional",
     "G4:1 G4 G4 D4 E4 E4 D4:2 B4:1 B4 A4 A4 G4:3 D4:1 "
     "G4:1 G4 G4 D4 E4 E4 D4:2 B4:1 B4 A4 A4 G4:3"),
    ("Auld Lang Syne", "Traditional (Scottish)",
     "C4:1 F4:1.5 E4:0.5 F4:1 A4 G4:1.5 F4:0.5 G4:1 A4 F4:1.5 F4:0.5 A4:1 C5 D5:3 "
     "D5:1 C5:1.5 A4:0.5 A4:1 F4 G4:1.5 F4:0.5 G4:1 A4 F4:1.5 D4:0.5 D4:1 C4 F4:3"),
    ("Joy to the World", "G. F. Handel (arr. Lowell Mason)",
     "C5:1 B4:0.75 A4:0.25 G4:1.5 F4:0.5 E4:1 D4 C4:1.5 G4:0.5 A4:1.5 A4:0.5 B4:1.5 B4:0.5 C5:3"),
    ("Hot Cross Buns", "Traditional",
     "E4:1 D4 C4:2 E4:1 D4 C4:2 C4:0.5 C4 C4 C4 D4 D4 D4 D4 E4:1 D4 C4:2"),
    ("The Star-Spangled Banner", "John Stafford Smith",
     "G4:0.75 E4:0.25 C4:1 E4 G4 C5:2 E5:0.75 D5:0.25 C5:1 E4 F#4 G4:2 "
     "G4:0.5 G4 E5:1.5 D5:0.5 C5:1 B4:2 A4:0.75 B4:0.25 C5:1 C5 G4 E4 C4"),
    ("Minuet in G", "Christian Petzold (attr. J. S. Bach)",
     "D5:1 G4:0.5 A4 B4 C5 D5:1 G4 G4 E5:1 C5:0.5 D5 E5 F#5 G5:1 G4 G4 "
     "C5:1 D5:0.5 C5 B4 A4 B4:1 C5:0.5 B4 A4 G4 F#4:1 G4:0.5 A4 B4 G4 A4:3"),
    ("In the Hall of the Mountain King", "Edvard Grieg",
     "B3:0.5 C#4 D4 E4 F#4 D4 F#4:1 F4:0.5 C#4 F4:1 E4:0.5 C4 E4:1 "
     "B3:0.5 C#4 D4 E4 F#4 D4 F#4 B4 A4 F#4 D4 F#4 A4:2"),
    ("Oh! Susanna", "Stephen Foster",
     "C4:0.5 D4 E4:1 G4 G4:1.5 A4:0.5 G4:1 E4 C4:1.5 D4:0.5 E4:1 E4 D4 C4 D4:3 "
     "C4:0.5 D4 E4:1 G4 G4:1.5 A4:0.5 G4:1 E4 C4:1.5 D4:0.5 E4:1 E4 D4 D4 C4:4"),
    ("Silent Night", "Franz Xaver Gruber",
     "G4:1.5 A4:0.5 G4:1 E4:3 G4:1.5 A4:0.5 G4:1 E4:3 D5:2 D5:1 B4:3 C5:2 C5:1 G4:3 "
     "A4:2 A4:1 C5:1.5 B4:0.5 A4:1 G4:1.5 A4:0.5 G4:1 E4:3"),
    ("We Wish You a Merry Christmas", "Traditional (English)",
     "D4:1 G4:1 G4:0.5 A4 G4 F#4 E4:1 E4 E4 A4:1 A4:0.5 B4 A4 G4 F#4:1 D4 D4 "
     "B4:1 B4:0.5 C5 B4 A4 G4:1 E4 D4:0.5 D4 E4:1 A4 F#4 G4:2"),
    ("Brahms' Lullaby", "Johannes Brahms",
     "E4:0.5 E4 G4:2 E4:0.5 E4 G4:2 E4:0.5 G4 C5:1 B4:1.5 A4:0.5 A4:1 G4 "
     "D4:0.5 E4 F4:1 D4 D4:0.5 E4 F4:2 D4:0.5 F4 B4:0.5 A4 G4:1 B4 C5:2"),
    ("Turkish March (Rondo alla Turca)", "W. A. Mozart",
     "B4:0.25 A4 G#4 A4 C5:1 D5:0.25 C5 B4 C5 E5:1 F5:0.25 E5 D#5 E5 "
     "B5 A5 G#5 A5 B5 A5 G#5 A5 C6:1"),
    ("Swan Lake (Scene theme)", "Pyotr Ilyich Tchaikovsky",
     "F#4:4 B3:1 C#4 D4 E4 F#4:3 D4:1 F#4:3 D4:1 F#4:3 B3:1 D4 B3 G3 D4 B3:4"),
    ("Canon in D (melody)", "Johann Pachelbel",
     "F#5:2 E5 D5 C#5 B4 A4 B4 C#5 D5 C#5 B4 A4 G4 F#4 G4 E4"),
    ("Scarborough Fair", "Traditional (English)",
     "D4:2 D4:1 A4:2 A4:1 E4:1.5 F4:0.5 E4:1 D4:3 r:1 A4:1 C5 D5:2 C5:1 A4:1 B4 G4 A4:3"),
    ("House of the Rising Sun", "Traditional (American folk)",
     "A3:1 C4:1 D4:1 E4:2 E4:1 D4:1 C4:1 A3:2 C4:1 A3:1 G3:1 A3:3"),
    ("Yankee Doodle", "Traditional (American)",
     "C4:1 C4 D4 E4 C4 E4 D4 G3 C4 C4 D4 E4 C4:2 B3:2 C4:1 C4 D4 E4 F4 E4 D4 C4 B3 G3 A3 B3 C4:2 C4:2"),
    ("Deck the Halls", "Traditional (Welsh)",
     "C5:1.5 Bb4:0.5 A4:1 G4 F4 G4 A4 F4 G4:0.5 A4 Bb4 G4 A4:1.5 G4:0.5 F4:1 E4 F4:2"),
]
