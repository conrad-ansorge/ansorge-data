<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:html="http://www.w3.org/1999/xhtml"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs">

    <xsl:output method="xml" encoding="UTF-8" indent="yes"/>

    <!-- Identity template: kopiere alles unverändert -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- Verarbeite Tabellen: fasse mehrzeilige Events zusammen -->
    <xsl:template match="html:table">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:apply-templates select="html:tr" mode="merge-rows"/>
        </xsl:copy>
    </xsl:template>

    <!-- Verarbeite Tabellenzeilen -->
    <xsl:template match="html:tr" mode="merge-rows">
        <xsl:choose>
            <!-- Zeile mit Datum: sammle Fortsetzungszeilen -->
            <xsl:when test="count(html:td) >= 4 and normalize-space(html:td[1]) != ''">
                <!-- Finde alle folgenden Zeilen ohne Datum -->
                <xsl:variable name="continuation-rows" select="following-sibling::html:tr[
                    count(html:td) >= 4 and
                    (normalize-space(html:td[1]) = '' or html:td[1][not(normalize-space(.))])
                ][not(preceding-sibling::html:tr[
                    count(html:td) >= 4 and
                    normalize-space(html:td[1]) != '' and
                    generate-id() != generate-id(current())
                ][1] >> .)]"/>

                <xsl:copy>
                    <xsl:apply-templates select="@*"/>

                    <!-- Für jede Spalte: kombiniere aktuelle und Fortsetzungszeilen -->
                    <xsl:for-each select="html:td">
                        <xsl:variable name="col-pos" select="position()"/>
                        <xsl:variable name="continuation-cells" select="$continuation-rows/html:td[$col-pos]"/>

                        <xsl:copy>
                            <xsl:apply-templates select="@*"/>
                            <!-- Aktuelle Zelle -->
                            <xsl:apply-templates select="node()"/>
                            <!-- Fortsetzungszellen: nur nicht-leere Absätze -->
                            <xsl:for-each select="$continuation-cells/html:p[normalize-space(.) != '']">
                                <xsl:copy-of select="."/>
                            </xsl:for-each>
                        </xsl:copy>
                    </xsl:for-each>
                </xsl:copy>
            </xsl:when>

            <!-- Fortsetzungszeilen: überspringen (wurden schon verarbeitet) -->
            <xsl:when test="count(html:td) >= 4 and
                           (normalize-space(html:td[1]) = '' or html:td[1][not(normalize-space(.))]) and
                           preceding-sibling::html:tr[count(html:td) >= 4 and normalize-space(html:td[1]) != '']"/>

            <!-- Andere Zeilen: kopieren -->
            <xsl:otherwise>
                <xsl:copy>
                    <xsl:apply-templates select="@* | node()"/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
