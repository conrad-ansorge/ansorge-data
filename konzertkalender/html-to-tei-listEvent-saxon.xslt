<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:html="http://www.w3.org/1999/xhtml" xmlns:ansorge="http://ansorge.local"
    exclude-result-prefixes="xs html ansorge">
    <xsl:output method="xml" encoding="UTF-8" indent="yes"/>
    <!-- Root template -->
    <xsl:template match="/">
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <titleStmt>
                        <title>Conrad Ansorge Konzertkalender 1879-1943</title>
                        <author>Christian Heitler</author>
                        <respStmt>
                            <resp>Mitwirkung</resp>
                            <name>Eike Rathgeber</name>
                            <name>Manuela Schwartz</name>
                            <name>Caroline Sibilak</name>
                        </respStmt>
                    </titleStmt>
                    <publicationStmt>
                        <p>Konvertiert aus HTML zu TEI</p>
                    </publicationStmt>
                    <sourceDesc>
                        <p>Erstellt aus HTML-Export des Konzertkalenders</p>
                    </sourceDesc>
                </fileDesc>
            </teiHeader>
            <text>
                <body>
                    <listEvent>
                        <!-- Alle Zeilen verarbeiten: Überschriften und Events -->
                        <xsl:apply-templates select="//html:table"/>
                    </listEvent>
                </body>
            </text>
        </TEI>
    </xsl:template>
    <xsl:template match="html:table">
        <xsl:element name="listEvent" namespace="http://www.tei-c.org/ns/1.0">
            <xsl:if test="html:tr[1][not(html:td[2])]">
                <head xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:apply-templates select="html:tr[1]/html:td//html:p" mode="mixed-content"/>
                </head>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    <!-- Template for table rows - unterscheide Überschriften und Events -->
    <xsl:template match="html:tr[html:td[normalize-space(.) != '']]">
        <xsl:choose>
            <!-- Überschriften: 1. Zeile einer Tabelle -->
            <xsl:when test="not(preceding-sibling::html:tr) and not(html:td[2])"/>

            <!-- Überspringe Fortsetzungszeilen (werden vom Haupt-Event verarbeitet) -->
            <xsl:when test="count(html:td) >= 4 and
                           (normalize-space(html:td[1]) = '' or html:td[1][not(normalize-space(.))]) and
                           preceding-sibling::html:tr[count(html:td) >= 4 and normalize-space(html:td[1]) != '']"/>

            <!-- Konzert-Events: Zeilen mit 4+ td-Elementen UND Datum -->
            <xsl:when test="count(html:td) >= 4 and normalize-space(html:td[1]) != ''">
                <!-- Sammle alle folgenden Zeilen ohne Datum (Fortsetzungen) -->
                <xsl:variable name="continuation-rows" as="element()*">
                    <xsl:call-template name="collect-continuation-rows">
                        <xsl:with-param name="current-row" select="."/>
                    </xsl:call-template>
                </xsl:variable>

                <xsl:variable name="date-text" select="normalize-space(html:td[1])"/>
                <xsl:variable name="parsed-date" select="ansorge:parse-date($date-text)"/>
                <xsl:variable name="eventName" select="normalize-space(html:td[3])"/>
                <event xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="when">
                        <xsl:value-of select="$parsed-date"/>
                    </xsl:attribute>
                    <xsl:attribute name="xml:id">
                        <xsl:text>ansorge_e_</xsl:text>
                        <xsl:number
                            count="html:tr[html:td[normalize-space(.) != '']][not(count(html:td) = 1 and html:td[@colspan &gt;= 4])]"
                            level="any"/>
                    </xsl:attribute>
                    <xsl:element name="eventName" namespace="http://www.tei-c.org/ns/1.0">
                        <xsl:value-of select="$eventName"/>
                    </xsl:element>
                    <xsl:element name="desc" namespace="http://www.tei-c.org/ns/1.0">
                        <xsl:attribute name="type">
                            <xsl:text>date</xsl:text>
                        </xsl:attribute>
                        <xsl:value-of select="$date-text"/>
                    </xsl:element>
                    <!-- Location (Spalte 2) - kombiniere mit Fortsetzungszeilen -->
                    <xsl:variable name="all-location-cells" select="html:td[2] | $continuation-rows/html:td[2]"/>
                    <xsl:if test="$all-location-cells//html:p[normalize-space(.) != '']">
                        <xsl:element name="place" namespace="http://www.tei-c.org/ns/1.0">
                            <placeName xmlns="http://www.tei-c.org/ns/1.0">
                                <xsl:apply-templates select="$all-location-cells//html:p" mode="kein-p"/>
                            </placeName>
                        </xsl:element>
                    </xsl:if>

                    <!-- Event description (Spalte 3) - kombiniere mit Fortsetzungszeilen -->
                    <!--<xsl:variable name="all-event-cells" select="html:td[3] | $continuation-rows/html:td[3]"/>
                    <xsl:if test="$all-event-cells//html:p[normalize-space(.) != '']">
                        <desc type="event">
                            <xsl:apply-templates select="$all-event-cells//html:p" mode="mixed-content"/>
                        </desc>
                    </xsl:if>-->

                    <!-- Program (Spalte 4) - kombiniere mit Fortsetzungszeilen -->
                    <xsl:variable name="all-program-cells" select="html:td[4] | $continuation-rows/html:td[4]"/>
                    <xsl:if test="$all-program-cells//html:p[normalize-space(.) != '']">
                        <desc type="program">
                            <xsl:call-template name="merge-program-cells">
                                <xsl:with-param name="cells" select="$all-program-cells"/>
                            </xsl:call-template>
                        </desc>
                    </xsl:if>
                </event>
            </xsl:when>
            <!-- Lebensereignisse: Zeilen mit nur 1-3 td-Elementen -->
            <xsl:otherwise>
                <event xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="xml:id">
                        <xsl:text>ansorge_e_</xsl:text>
                        <xsl:number
                            count="html:tr[html:td[normalize-space(.) != '']][not(count(html:td) = 1 and html:td[@colspan &gt;= 4])]"
                            level="any"/>
                    </xsl:attribute>
                    <xsl:attribute name="type">
                        <xsl:text>life-event</xsl:text>
                    </xsl:attribute>
                    <desc type="life-event">
                        <xsl:for-each select="html:td">
                            <xsl:apply-templates select=".//html:p" mode="mixed-content"/>
                        </xsl:for-each>
                    </desc>
                </event>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <!-- Mixed content mode: preserve paragraphs and formatting -->
    <xsl:template match="html:p" mode="mixed-content">
        <xsl:choose>
            <!-- If there are multiple p elements, wrap each in <p> -->
            <xsl:when test="count(../html:p) > 1">
                <p xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:apply-templates mode="inline"/>
                </p>
            </xsl:when>
            <!-- If only one p, don't wrap -->
            <xsl:otherwise>
                <xsl:apply-templates mode="inline"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <xsl:template match="html:p" mode="kein-p">
        <xsl:choose>
            <!-- If there are multiple p elements, wrap each in <p> -->
            <xsl:when test="count(../html:p) > 1">
                
                    <xsl:apply-templates mode="inline"/>
                <xsl:text> </xsl:text>
            </xsl:when>
            <!-- If only one p, don't wrap -->
            <xsl:otherwise>
                <xsl:apply-templates mode="inline"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <!-- Inline mode: process text and formatting -->
    <xsl:template match="html:i" mode="inline">
        <hi xmlns="http://www.tei-c.org/ns/1.0" rend="italic">
            <xsl:apply-templates mode="inline"/>
        </hi>
    </xsl:template>
    <xsl:template match="html:b | html:strong" mode="inline">
        <hi xmlns="http://www.tei-c.org/ns/1.0" rend="bold">
            <xsl:apply-templates mode="inline"/>
        </hi>
    </xsl:template>
    <xsl:template match="html:u" mode="inline">
        <hi xmlns="http://www.tei-c.org/ns/1.0" rend="underline">
            <xsl:apply-templates mode="inline"/>
        </hi>
    </xsl:template>
    <xsl:template match="html:br" mode="inline">
        <lb xmlns="http://www.tei-c.org/ns/1.0"/>
    </xsl:template>
    <!-- Superscript -->
    <xsl:template match="html:sup" mode="inline">
        <hi xmlns="http://www.tei-c.org/ns/1.0" rend="superscript">
            <xsl:apply-templates mode="inline"/>
        </hi>
    </xsl:template>
    <!-- Subscript -->
    <xsl:template match="html:sub" mode="inline">
        <hi xmlns="http://www.tei-c.org/ns/1.0" rend="subscript">
            <xsl:apply-templates mode="inline"/>
        </hi>
    </xsl:template>
    <!-- Text nodes in inline mode -->
    <xsl:template match="text()" mode="inline">
        <xsl:value-of select="."/>
    </xsl:template>
    <!-- Default template to ignore unmatched elements -->
    <xsl:template match="*" mode="inline">
        <xsl:apply-templates mode="inline"/>
    </xsl:template>
    <!-- Hilfsfunktion zum Sammeln von Fortsetzungszeilen -->
    <xsl:template name="collect-continuation-rows">
        <xsl:param name="current-row"/>
        <!-- Finde alle folgenden Zeilen ohne Datum, bis zur nächsten Zeile mit Datum -->
        <xsl:variable name="next-event-row" select="$current-row/following-sibling::html:tr[
            count(html:td) >= 4 and normalize-space(html:td[1]) != ''
        ][1]"/>

        <xsl:choose>
            <xsl:when test="$next-event-row">
                <!-- Nimm alle Zeilen zwischen current-row und next-event-row -->
                <xsl:sequence select="$current-row/following-sibling::html:tr[
                    count(html:td) >= 4 and
                    (normalize-space(html:td[1]) = '' or html:td[1][not(normalize-space(.))]) and
                    . &lt;&lt; $next-event-row
                ]"/>
            </xsl:when>
            <xsl:otherwise>
                <!-- Nimm alle verbleibenden Fortsetzungszeilen -->
                <xsl:sequence select="$current-row/following-sibling::html:tr[
                    count(html:td) >= 4 and
                    (normalize-space(html:td[1]) = '' or html:td[1][not(normalize-space(.))])
                ]"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- Hilfsfunktion zum Zusammenführen von Programm-Zellen -->
    <xsl:template name="merge-program-cells">
        <xsl:param name="cells"/>
        <list xmlns="http://www.tei-c.org/ns/1.0">
            <xsl:call-template name="process-program-paragraphs">
                <xsl:with-param name="paragraphs" select="$cells//html:p"/>
            </xsl:call-template>
        </list>
    </xsl:template>

    <!-- Date parsing function -->
    <xsl:function name="ansorge:parse-date" as="xs:string">
        <xsl:param name="date-string" as="xs:string"/>
        <xsl:variable name="clean-date" select="normalize-space($date-string)"/>
        <xsl:choose>
            <!-- Format: DD.MM.YYYY -->
            <xsl:when test="matches($clean-date, '^\d{2}\.\d{2}\.\d{4}$')">
                <xsl:variable name="parts" select="tokenize($clean-date, '\.')"/>
                <xsl:value-of select="concat($parts[3], '-', $parts[2], '-', $parts[1])"/>
            </xsl:when>
            <!-- Format: DD.MM.YY (19XX or 18XX) -->
            <xsl:when test="matches($clean-date, '^\d{2}\.\d{2}\.\d{2}$')">
                <xsl:variable name="parts" select="tokenize($clean-date, '\.')"/>
                <xsl:variable name="year" select="xs:integer($parts[3])"/>
                <xsl:variable name="full-year">
                    <xsl:choose>
                        <xsl:when test="$year &lt; 50">
                            <xsl:value-of select="1900 + $year"/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="1800 + $year"/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:variable>
                <xsl:value-of select="concat($full-year, '-', $parts[2], '-', $parts[1])"/>
            </xsl:when>
            <!-- Format: MM.YYYY or MM/YYYY -->
            <xsl:when test="matches($clean-date, '^\d{2}[./]\d{4}$')">
                <xsl:variable name="parts" select="tokenize($clean-date, '[./]')"/>
                <xsl:value-of select="concat($parts[2], '-', $parts[1])"/>
            </xsl:when>
            <!-- Format: YYYY -->
            <xsl:when test="matches($clean-date, '^\d{4}$')">
                <xsl:value-of select="$clean-date"/>
            </xsl:when>
            <!-- Cannot parse -->
            <xsl:otherwise>
                <xsl:value-of select="''"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>
    
    <!-- Template für Programminhalt: Konvertiere zu list mit strukturierten items -->
    <xsl:template match="html:td" mode="program">
        <list xmlns="http://www.tei-c.org/ns/1.0">
            <xsl:call-template name="process-program-paragraphs">
                <xsl:with-param name="paragraphs" select=".//html:p"/>
            </xsl:call-template>
        </list>
    </xsl:template>

    <!-- Template zum Verarbeiten von Absätzen mit Silbentrennung -->
    <xsl:template name="process-program-paragraphs">
        <xsl:param name="paragraphs"/>
        <xsl:param name="position" select="1"/>
        <xsl:param name="accumulated-text" select="''"/>
        <xsl:param name="accumulated-nodes" as="node()*"/>

        <xsl:choose>
            <xsl:when test="$position &lt;= count($paragraphs)">
                <xsl:variable name="current-p" select="$paragraphs[$position]"/>
                <xsl:variable name="current-text">
                    <xsl:apply-templates select="$current-p" mode="inline"/>
                </xsl:variable>
                <xsl:variable name="current-normalized" select="normalize-space($current-text)"/>

                <xsl:choose>
                    <!-- Wenn aktueller Absatz mit Bindestrich endet und nächster mit Kleinbuchstaben beginnt -->
                    <xsl:when test="ends-with($current-normalized, '-') and $position &lt; count($paragraphs)">
                        <xsl:variable name="next-p" select="$paragraphs[$position + 1]"/>
                        <xsl:variable name="next-text">
                            <xsl:apply-templates select="$next-p" mode="inline"/>
                        </xsl:variable>
                        <xsl:variable name="next-normalized" select="normalize-space($next-text)"/>

                        <xsl:choose>
                            <!-- Nächster Absatz beginnt mit Kleinbuchstaben: zusammenführen -->
                            <xsl:when test="matches($next-normalized, '^[a-zäöüß]')">
                                <!-- Akkumuliere den Text (ohne Bindestrich) -->
                                <xsl:call-template name="process-program-paragraphs">
                                    <xsl:with-param name="paragraphs" select="$paragraphs"/>
                                    <xsl:with-param name="position" select="$position + 1"/>
                                    <xsl:with-param name="accumulated-text"
                                        select="concat($accumulated-text, substring($current-normalized, 1, string-length($current-normalized) - 1))"/>
                                    <xsl:with-param name="accumulated-nodes" select="($accumulated-nodes, $current-p/node())"/>
                                </xsl:call-template>
                            </xsl:when>
                            <!-- Nächster Absatz beginnt nicht mit Kleinbuchstaben: normales Item -->
                            <xsl:otherwise>
                                <!-- Verarbeite akkumulierten Text falls vorhanden -->
                                <xsl:if test="$accumulated-text != ''">
                                    <xsl:call-template name="create-program-item">
                                        <xsl:with-param name="text" select="concat($accumulated-text, $current-normalized)"/>
                                        <xsl:with-param name="nodes" select="$current-p/node()"/>
                                    </xsl:call-template>
                                </xsl:if>
                                <!-- Verarbeite aktuellen Absatz wenn kein akkumulierter Text -->
                                <xsl:if test="$accumulated-text = ''">
                                    <xsl:apply-templates select="$current-p" mode="program-item"/>
                                </xsl:if>
                                <!-- Weiter mit nächstem Absatz -->
                                <xsl:call-template name="process-program-paragraphs">
                                    <xsl:with-param name="paragraphs" select="$paragraphs"/>
                                    <xsl:with-param name="position" select="$position + 1"/>
                                </xsl:call-template>
                            </xsl:otherwise>
                        </xsl:choose>
                    </xsl:when>

                    <!-- Aktueller Absatz ist Fortsetzung einer Silbentrennung -->
                    <xsl:when test="$accumulated-text != ''">
                        <!-- Füge zusammen und erstelle Item -->
                        <xsl:call-template name="create-program-item">
                            <xsl:with-param name="text" select="concat($accumulated-text, $current-normalized)"/>
                            <xsl:with-param name="nodes" select="$current-p/node()"/>
                        </xsl:call-template>
                        <!-- Weiter mit nächstem Absatz -->
                        <xsl:call-template name="process-program-paragraphs">
                            <xsl:with-param name="paragraphs" select="$paragraphs"/>
                            <xsl:with-param name="position" select="$position + 1"/>
                        </xsl:call-template>
                    </xsl:when>

                    <!-- Normaler Absatz -->
                    <xsl:otherwise>
                        <xsl:apply-templates select="$current-p" mode="program-item"/>
                        <xsl:call-template name="process-program-paragraphs">
                            <xsl:with-param name="paragraphs" select="$paragraphs"/>
                            <xsl:with-param name="position" select="$position + 1"/>
                        </xsl:call-template>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:when>
        </xsl:choose>
    </xsl:template>

    <!-- Hilfsfunktion zum Erstellen eines Program-Items aus zusammengeführtem Text -->
    <xsl:template name="create-program-item">
        <xsl:param name="text"/>
        <xsl:param name="nodes"/>

        <xsl:if test="$text != ''">
            <xsl:call-template name="split-program-entries">
                <xsl:with-param name="text" select="$text"/>
                <xsl:with-param name="nodes" select="$nodes"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>

    <!-- Template für einzelne Programm-Items -->
    <xsl:template match="html:p" mode="program-item">
        <xsl:variable name="text-content">
            <xsl:apply-templates mode="inline"/>
        </xsl:variable>
        <xsl:variable name="text" select="normalize-space($text-content)"/>

        <!-- Überspringe leere Absätze -->
        <xsl:if test="$text != ''">
            <xsl:choose>
                <!-- Prüfe ob es eine reine Abschnittsnummer ist (z.B. "I.", "II.") -->
                <xsl:when test="matches($text, '^(I{1,3}V?|IV|V|VI{0,3})\.$')">
                    <item xmlns="http://www.tei-c.org/ns/1.0">
                        <xsl:apply-templates mode="inline"/>
                    </item>
                </xsl:when>

                <!-- Prüfe ob es eine Abschnittsüberschrift ist (z.B. "I. Theil", "II. Theil") -->
                <xsl:when test="matches($text, '^(I{1,3}V?|IV|V|VI{0,3})\.\s*(Theil|Teil|Part)', 'i')">
                    <item xmlns="http://www.tei-c.org/ns/1.0">
                        <xsl:apply-templates mode="inline"/>
                    </item>
                </xsl:when>

                <!-- Normaler Eintrag: kann mehrere Werke enthalten, durch Doppelpunkt getrennt -->
                <xsl:otherwise>
                    <xsl:call-template name="split-program-entries">
                        <xsl:with-param name="text" select="$text"/>
                        <xsl:with-param name="nodes" select="node()"/>
                    </xsl:call-template>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:if>
    </xsl:template>

    <!-- Template zum Aufteilen von Programmeinträgen bei mehreren Werken -->
    <xsl:template name="split-program-entries">
        <xsl:param name="text"/>
        <xsl:param name="nodes"/>

        <item xmlns="http://www.tei-c.org/ns/1.0">
            <xsl:choose>
                <!-- Wenn Doppelpunkt vorhanden: Person und Werk trennen -->
                <xsl:when test="contains($text, ':')">
                    <!-- Person(en) vor dem Doppelpunkt -->
                    <rs type="person">
                        <xsl:call-template name="extract-before-colon">
                            <xsl:with-param name="nodes" select="$nodes"/>
                        </xsl:call-template>
                    </rs>

                    <!-- Werk nach dem Doppelpunkt (ohne Doppelpunkt) -->
                    <rs type="work">
                        <xsl:call-template name="extract-after-colon">
                            <xsl:with-param name="nodes" select="$nodes"/>
                        </xsl:call-template>
                    </rs>
                </xsl:when>

                <!-- Kein Doppelpunkt: gesamter Text ist ein Werk -->
                <xsl:otherwise>
                    <rs type="work">
                        <xsl:apply-templates select="$nodes" mode="inline"/>
                    </rs>
                </xsl:otherwise>
            </xsl:choose>
        </item>
    </xsl:template>

    <!-- Hilfstemplates zum Extrahieren von Text vor/nach Doppelpunkt mit Formatierung -->
    <xsl:template name="extract-before-colon">
        <xsl:param name="nodes"/>
        <xsl:param name="found-colon" select="false()"/>

        <xsl:for-each select="$nodes">
            <xsl:choose>
                <xsl:when test="self::text()">
                    <xsl:choose>
                        <xsl:when test="contains(., ':')">
                            <xsl:value-of select="substring-before(., ':')"/>
                        </xsl:when>
                        <xsl:when test="not($found-colon)">
                            <xsl:value-of select="."/>
                        </xsl:when>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::html:i and not($found-colon)">
                    <hi xmlns="http://www.tei-c.org/ns/1.0" rend="italic">
                        <xsl:call-template name="extract-before-colon">
                            <xsl:with-param name="nodes" select="node()"/>
                            <xsl:with-param name="found-colon" select="$found-colon"/>
                        </xsl:call-template>
                    </hi>
                </xsl:when>
                <xsl:when test="self::html:b and not($found-colon)">
                    <hi xmlns="http://www.tei-c.org/ns/1.0" rend="bold">
                        <xsl:call-template name="extract-before-colon">
                            <xsl:with-param name="nodes" select="node()"/>
                            <xsl:with-param name="found-colon" select="$found-colon"/>
                        </xsl:call-template>
                    </hi>
                </xsl:when>
            </xsl:choose>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="extract-after-colon">
        <xsl:param name="nodes"/>
        <xsl:param name="found-colon" select="false()"/>

        <xsl:for-each select="$nodes">
            <xsl:choose>
                <xsl:when test="self::text()">
                    <xsl:choose>
                        <xsl:when test="contains(., ':')">
                            <xsl:value-of select="substring-after(., ':')"/>
                        </xsl:when>
                        <xsl:when test="$found-colon">
                            <xsl:value-of select="."/>
                        </xsl:when>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::html:i and $found-colon">
                    <hi xmlns="http://www.tei-c.org/ns/1.0" rend="italic">
                        <xsl:call-template name="extract-after-colon">
                            <xsl:with-param name="nodes" select="node()"/>
                            <xsl:with-param name="found-colon" select="true()"/>
                        </xsl:call-template>
                    </hi>
                </xsl:when>
                <xsl:when test="self::html:b and $found-colon">
                    <hi xmlns="http://www.tei-c.org/ns/1.0" rend="bold">
                        <xsl:call-template name="extract-after-colon">
                            <xsl:with-param name="nodes" select="node()"/>
                            <xsl:with-param name="found-colon" select="true()"/>
                        </xsl:call-template>
                    </hi>
                </xsl:when>
            </xsl:choose>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>
