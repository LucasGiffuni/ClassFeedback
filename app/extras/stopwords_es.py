"""Stopwords en español: artículos, preposiciones, pronombres, conjunciones,
adverbios frecuentes y formas comunes de ser, estar, haber y tener.

Se comparan sin tildes, por lo que basta una variante de cada palabra.
"""

STOPWORDS = frozenset("""
a al algo algun alguna algunas alguno algunos ambos ante antes aquel aquella
aquellas aquello aquellos aqui asi aun aunque bajo cada casi como con contra
cual cuales cualquier cuan cuando cuanto cuanta cuantos cuantas de del desde
donde dos durante e el ella ellas ello ellos en entonces entre era eramos eran
eras eres es esa esas ese eso esos esta estaba estabamos estaban estabas
estad estada estadas estado estados estais estamos estan estando estar estara
estaran estaras estare estareis estaremos estaria estariais estariamos
estarian estarias estas este esteis estemos esten estes esto estos estoy
estuve estuviera estuvierais estuvieramos estuvieran estuvieras estuvieron
estuviese estuvieseis estuviesemos estuviesen estuvieses estuvimos estuviste
estuvisteis estuvo fue fuera fuerais fueramos fueran fueras fueron fuese
fueseis fuesemos fuesen fueses fui fuimos fuiste fuisteis ha habeis habia
habiais habiamos habian habias habida habidas habido habidos habiendo habra
habran habras habre habreis habremos habria habriais habriamos habrian habrias
han has hasta hay haya hayais hayamos hayan hayas he hemos hube hubiera
hubierais hubieramos hubieran hubieras hubieron hubiese hubieseis hubiesemos
hubiesen hubieses hubimos hubiste hubisteis hubo la las le les lo los me mi
mia mias mientras mio mios mis mucha muchas mucho muchos muy nada ni ninguna
ninguno no nos nosotras nosotros nuestra nuestras nuestro nuestros o os otra
otras otro otros para pero poco pocos por porque pues que quien quienes se sea
seais seamos sean seas sentid sentida sentidas sentido sentidos sera seran
seras sere sereis seremos seria seriais seriamos serian serias ser si sido
siendo sin sino sobre sois somos son soy su sus suya suyas suyo suyos tal
tambien tampoco tan tanta tantas tanto tantos te tendra tendran tendras tendre
tendreis tendremos tendria tendriais tendriamos tendrian tendrias tened teneis
tenemos tener tenga tengais tengamos tengan tengas tengo tenia teniais teniamos
tenian tenias tenida tenidas tenido tenidos teniendo ti tiene tienen tienes
todo todos toda todas tu tus tuve tuviera tuvierais tuvieramos tuvieran
tuvieras tuvieron tuviese tuvieseis tuviesemos tuviesen tuvieses tuvimos
tuviste tuvisteis tuvo tuya tuyas tuyo tuyos u un una unas uno unos usted
ustedes vosotras vosotros vuestra vuestras vuestro vuestros y ya yo
mas menos solo tras via
""".split())
