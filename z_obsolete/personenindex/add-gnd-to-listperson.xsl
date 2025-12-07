<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="tei">

    <xsl:output method="xml" encoding="UTF-8" indent="yes"/>

    <!-- Load the GND matches from openrefine-match.xml -->
    <xsl:variable name="gnd-matches" select="document('openrefine-match.xml')/root/row"/>

    <!-- Identity template: copy everything by default -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- Match person elements and add GND idno -->
    <xsl:template match="tei:person">
        <xsl:variable name="person-id" select="@xml:id"/>
        <xsl:variable name="gnd-number" select="$gnd-matches[id = $person-id]/GND"/>

        <xsl:copy>
            <!-- Copy attributes -->
            <xsl:apply-templates select="@*"/>

            <!-- Copy persName elements -->
            <xsl:apply-templates select="tei:persName"/>

            <!-- Add GND idno if available and not already present -->
            <xsl:if test="$gnd-number and string-length($gnd-number) &gt; 0">
                <xsl:choose>
                    <!-- Update existing GND idno -->
                    <xsl:when test="tei:idno[@type='gnd']">
                        <xsl:apply-templates select="tei:idno[@type='gnd']" mode="update">
                            <xsl:with-param name="new-gnd" select="$gnd-number"/>
                        </xsl:apply-templates>
                    </xsl:when>
                    <!-- Add new GND idno -->
                    <xsl:otherwise>
                        <idno type="gnd">
                            <xsl:value-of select="$gnd-number"/>
                        </idno>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:if>

            <!-- Copy existing idno elements (except GND which was handled above) -->
            <xsl:apply-templates select="tei:idno[not(@type='gnd')]"/>

            <!-- Copy all other elements -->
            <xsl:apply-templates select="node()[not(self::tei:persName) and not(self::tei:idno)]"/>
        </xsl:copy>
    </xsl:template>

    <!-- Template to update existing GND idno -->
    <xsl:template match="tei:idno[@type='gnd']" mode="update">
        <xsl:param name="new-gnd"/>
        <idno type="gnd">
            <xsl:value-of select="$new-gnd"/>
        </idno>
    </xsl:template>

</xsl:stylesheet>
