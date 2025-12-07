<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="tei xs">

    <xsl:output method="html" html-version="5.0" indent="yes" encoding="UTF-8"/>

    <!-- Root template -->
    <xsl:template match="/">
        <html lang="de">
            <head>
                <meta charset="UTF-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
                <title>Personenregister Conrad Ansorge</title>

                <!-- Bootstrap CSS -->
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>

                <style>
                    body {
                        padding-top: 20px;
                        padding-bottom: 40px;
                    }
                    .person-card {
                        margin-bottom: 20px;
                        scroll-margin-top: 80px;
                    }
                    .person-name {
                        color: #0d6efd;
                    }
                    .person-dates {
                        color: #6c757d;
                        font-style: italic;
                    }
                    .person-variant {
                        font-size: 0.9em;
                        color: #6c757d;
                    }
                    .page-ref {
                        display: inline-block;
                        margin: 2px;
                    }
                    .navbar {
                        margin-bottom: 30px;
                    }
                    .alphabet-nav {
                        position: sticky;
                        top: 0;
                        background: white;
                        z-index: 1000;
                        padding: 10px 0;
                        border-bottom: 1px solid #dee2e6;
                        margin-bottom: 20px;
                    }
                    .alphabet-nav a {
                        margin: 0 5px;
                        text-decoration: none;
                    }
                    .ref-section, .org-section {
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 2px solid #dee2e6;
                    }
                </style>
            </head>
            <body>
                <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
                    <div class="container-fluid">
                        <a class="navbar-brand" href="#">Personenregister Conrad Ansorge</a>
                        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                            <span class="navbar-toggler-icon"></span>
                        </button>
                        <div class="collapse navbar-collapse" id="navbarNav">
                            <ul class="navbar-nav">
                                <li class="nav-item">
                                    <a class="nav-link" href="#persons">Personen</a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="#references">Verweise</a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" href="#organizations">Organisationen</a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </nav>

                <div class="container">
                    <!-- Alphabet Navigation -->
                    <div class="alphabet-nav text-center">
                        <xsl:call-template name="alphabetNav"/>
                    </div>

                    <!-- Personen -->
                    <section id="persons">
                        <h1 class="mb-4">Personen</h1>
                        <xsl:apply-templates select="//tei:listPerson/tei:person">
                            <xsl:sort select="tei:persName[1]/tei:surname"/>
                        </xsl:apply-templates>
                    </section>

                    <!-- Verweise -->
                    <section id="references" class="ref-section">
                        <h2 class="mb-4">Verweise</h2>
                        <div class="list-group">
                            <xsl:apply-templates select="//tei:div[@type='references']//tei:ref"/>
                        </div>
                    </section>

                    <!-- Organisationen -->
                    <section id="organizations" class="org-section">
                        <h2 class="mb-4">Organisationen</h2>
                        <xsl:apply-templates select="//tei:listOrg/tei:org"/>
                    </section>
                </div>

                <!-- Bootstrap JS -->
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
            </body>
        </html>
    </xsl:template>

    <!-- Alphabet Navigation Template -->
    <xsl:template name="alphabetNav">
        <xsl:variable name="alphabet" select="('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z')"/>
        <xsl:for-each select="$alphabet">
            <a href="#letter-{.}" class="btn btn-sm btn-outline-primary">
                <xsl:value-of select="."/>
            </a>
        </xsl:for-each>
    </xsl:template>
    

    <!-- Person Template -->
    <xsl:template match="tei:person">
        <!-- Normalize diacritics and umlauts: Ż→Z, Ź→Z, Ä→A, Ö→O, Ü→U, etc. -->
        <xsl:variable name="rawFirstLetter" select="upper-case(substring(tei:persName[1]/tei:surname, 1, 1))"/>
        <xsl:variable name="firstLetter" select="
            if ($rawFirstLetter = 'Ä') then 'A'
            else if ($rawFirstLetter = 'Ö') then 'O'
            else if ($rawFirstLetter = 'Ü') then 'U'
            else translate($rawFirstLetter, 'ŻŹŽÇĆČŠŚŇÑ', 'ZZZCCCSSNÑ')"/>

        <!-- Add letter heading only for the first person with this letter -->
        <!-- Check if there are NO preceding siblings with the same first letter -->
        <xsl:variable name="currentLetter" select="$firstLetter"/>
        <xsl:if test="not(preceding-sibling::tei:person[
            let $raw := upper-case(substring(tei:persName[1]/tei:surname, 1, 1))
            return (if ($raw = 'Ä') then 'A'
                    else if ($raw = 'Ö') then 'O'
                    else if ($raw = 'Ü') then 'U'
                    else translate($raw, 'ŻŹŽÇĆČŠŚŇÑ', 'ZZZCCCSSNÑ')) = $currentLetter])">
            <h3 id="letter-{$firstLetter}" class="mt-5 mb-3" style="scroll-margin-top: 80px;">
                <xsl:value-of select="$firstLetter"/>
            </h3>
        </xsl:if>

        <div class="card person-card" id="{@xml:id}">
            <div class="card-body">
                <h5 class="card-title person-name">
                    <xsl:apply-templates select="tei:persName[1]"/>
                    <xsl:if test="tei:birth or tei:death">
                        <span class="person-dates ms-2">
                            <xsl:text>(</xsl:text>
                            <xsl:choose>
                                <xsl:when test="tei:birth and tei:death">
                                    <xsl:value-of select="tei:birth"/>
                                    <xsl:text>–</xsl:text>
                                    <xsl:value-of select="tei:death"/>
                                </xsl:when>
                                <xsl:when test="tei:birth">
                                    <xsl:text>*</xsl:text>
                                    <xsl:value-of select="tei:birth"/>
                                </xsl:when>
                                <xsl:when test="tei:death">
                                    <xsl:text>†</xsl:text>
                                    <xsl:value-of select="tei:death"/>
                                </xsl:when>
                            </xsl:choose>
                            <xsl:text>)</xsl:text>
                        </span>
                    </xsl:if>
                </h5>

                <!-- Namensvarianten -->
                <xsl:if test="tei:persName[@type]">
                    <div class="person-variant mb-2">
                        <xsl:for-each select="tei:persName[@type]">
                            <span class="badge bg-secondary me-1">
                                <xsl:choose>
                                    <xsl:when test="@type='eigentlich'">
                                        <xsl:text>eig. </xsl:text>
                                    </xsl:when>
                                    <xsl:when test="@type='geboren'">
                                        <xsl:text>geb. </xsl:text>
                                    </xsl:when>
                                    <xsl:when test="@type='verheiratet'">
                                        <xsl:text>verh. </xsl:text>
                                    </xsl:when>
                                </xsl:choose>
                                <xsl:apply-templates select="."/>
                            </span>
                        </xsl:for-each>
                    </div>
                </xsl:if>

                <!-- Normdaten Links (GND, Wikidata) -->
                <xsl:if test="tei:idno[@type='gnd'] or tei:idno[@type='wikidata']">
                    <div class="mb-2">
                        <xsl:if test="tei:idno[@type='gnd']">
                            <a href="https://d-nb.info/gnd/{tei:idno[@type='gnd']}"
                               target="_blank"
                               class="btn btn-sm btn-outline-secondary me-1"
                               title="GND: {tei:idno[@type='gnd']}">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" class="bi bi-link-45deg" viewBox="0 0 16 16">
                                    <path d="M4.715 6.542 3.343 7.914a3 3 0 1 0 4.243 4.243l1.828-1.829A3 3 0 0 0 8.586 5.5L8 6.086a1.002 1.002 0 0 0-.154.199 2 2 0 0 1 .861 3.337L6.88 11.45a2 2 0 1 1-2.83-2.83l.793-.792a4.018 4.018 0 0 1-.128-1.287z"/>
                                    <path d="M6.586 4.672A3 3 0 0 0 7.414 9.5l.775-.776a2 2 0 0 1-.896-3.346L9.12 3.55a2 2 0 1 1 2.83 2.83l-.793.792c.112.42.155.855.128 1.287l1.372-1.372a3 3 0 1 0-4.243-4.243z"/>
                                </svg>
                                GND
                            </a>
                        </xsl:if>
                        <xsl:if test="tei:idno[@type='wikidata']">
                            <a href="https://www.wikidata.org/wiki/{tei:idno[@type='wikidata']}"
                               target="_blank"
                               class="btn btn-sm btn-outline-secondary me-1"
                               title="Wikidata: {tei:idno[@type='wikidata']}">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" class="bi bi-globe" viewBox="0 0 16 16">
                                    <path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8m7.5-6.923c-.67.204-1.335.82-1.887 1.855A8 8 0 0 0 5.145 4H7.5zM4.09 4a9.3 9.3 0 0 1 .64-1.539 7 7 0 0 1 .597-.933A7.03 7.03 0 0 0 2.255 4zm-.582 3.5c.03-.877.138-1.718.312-2.5H1.674a7 7 0 0 0-.656 2.5zM4.847 5a12.5 12.5 0 0 0-.338 2.5H7.5V5zM8.5 5v2.5h2.99a12.5 12.5 0 0 0-.337-2.5zM4.51 8.5a12.5 12.5 0 0 0 .337 2.5H7.5V8.5zm3.99 0V11h2.653c.187-.765.306-1.608.338-2.5zM5.145 12q.208.58.468 1.068c.552 1.035 1.218 1.65 1.887 1.855V12zm.182 2.472a7 7 0 0 1-.597-.933A9.3 9.3 0 0 1 4.09 12H2.255a7 7 0 0 0 3.072 2.472M3.82 11a13.7 13.7 0 0 1-.312-2.5h-2.49c.062.89.291 1.733.656 2.5zm6.853 3.472A7 7 0 0 0 13.745 12H11.91a9.3 9.3 0 0 1-.64 1.539 7 7 0 0 1-.597.933M8.5 12v2.923c.67-.204 1.335-.82 1.887-1.855q.26-.487.468-1.068zm3.68-1h2.146c.365-.767.594-1.61.656-2.5h-2.49a13.7 13.7 0 0 1-.312 2.5m2.802-3.5a7 7 0 0 0-.656-2.5H12.18c.174.782.282 1.623.312 2.5zM11.27 2.461c.247.464.462.98.64 1.539h1.835a7 7 0 0 0-3.072-2.472c.218.284.418.598.597.933M10.855 4a8 8 0 0 0-.468-1.068C9.835 1.897 9.17 1.282 8.5 1.077V4z"/>
                                </svg>
                                Wikidata
                            </a>
                        </xsl:if>
                    </div>
                </xsl:if>

                <!-- Beschreibung -->
                <xsl:if test="tei:note[not(@type='page')]">
                    <p class="card-text">
                        <xsl:value-of select="tei:note[not(@type='page')]"/>
                    </p>
                </xsl:if>

                <!-- Seitenzahlen -->
                <xsl:if test="tei:bibl/tei:biblScope[@unit='page']">
                    <div class="mt-2">
                        <small class="text-muted">Seiten: </small>
                        <xsl:for-each select="tei:bibl/tei:biblScope[@unit='page']">
                            <span class="badge bg-light text-dark page-ref">
                                <xsl:value-of select="."/>
                            </span>
                        </xsl:for-each>
                    </div>
                </xsl:if>

                <!-- Verweise -->
                <xsl:if test=".//tei:ref[@type='see']">
                    <div class="mt-2">
                        <small class="text-muted">Siehe auch: </small>
                        <xsl:for-each select=".//tei:ref[@type='see']">
                            <span class="badge bg-info">
                                <xsl:value-of select="."/>
                            </span>
                        </xsl:for-each>
                    </div>
                </xsl:if>
            </div>
        </div>
    </xsl:template>

    <!-- persName Template -->
    <xsl:template match="tei:persName">
        <xsl:if test="tei:surname">
            <xsl:value-of select="tei:surname"/>
        </xsl:if>
        <xsl:if test="tei:forename">
            <xsl:text>, </xsl:text>
            <xsl:value-of select="tei:forename"/>
        </xsl:if>
        <xsl:if test="tei:name">
            <xsl:value-of select="tei:name"/>
        </xsl:if>
    </xsl:template>

    <!-- Reference Template -->
    <xsl:template match="tei:ref[@type='see']">
        <a href="#" class="list-group-item list-group-item-action" id="{@xml:id}">
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">
                    <xsl:value-of select="@source"/>
                </h6>
                <small>→</small>
            </div>
            <p class="mb-1">
                <xsl:text>siehe: </xsl:text>
                <strong><xsl:value-of select="@target"/></strong>
            </p>
        </a>
    </xsl:template>

    <!-- Organization Template -->
    <xsl:template match="tei:org">
        <div class="card person-card" id="{@xml:id}">
            <div class="card-body">
                <h5 class="card-title person-name">
                    <xsl:value-of select="tei:orgName"/>
                </h5>

                <!-- Beschreibung -->
                <xsl:if test="tei:note">
                    <p class="card-text">
                        <xsl:value-of select="tei:note"/>
                    </p>
                </xsl:if>

                <!-- Seitenzahlen -->
                <xsl:if test="tei:bibl/tei:biblScope[@unit='page']">
                    <div class="mt-2">
                        <small class="text-muted">Seiten: </small>
                        <xsl:for-each select="tei:bibl/tei:biblScope[@unit='page']">
                            <span class="badge bg-light text-dark page-ref">
                                <xsl:value-of select="."/>
                            </span>
                        </xsl:for-each>
                    </div>
                </xsl:if>
            </div>
        </div>
    </xsl:template>

</xsl:stylesheet>
