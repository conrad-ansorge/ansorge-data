<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:tei="http://www.tei-c.org/ns/1.0">

    <xsl:output method="text" encoding="UTF-8"/>

    <!-- Root template -->
    <xsl:template match="/">
        <!-- CSV Header -->
        <xsl:text>ID,Nachname,Vorname,Eigentlicher Name,GND,Wikidata,Geburtsjahr,Sterbejahr,Notiz,Seiten&#10;</xsl:text>

        <!-- Process all persons -->
        <xsl:apply-templates select="//tei:person"/>
    </xsl:template>

    <!-- Person template -->
    <xsl:template match="tei:person">
        <!-- ID -->
        <xsl:value-of select="@xml:id"/>
        <xsl:text>,</xsl:text>

        <!-- Nachname -->
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text" select="tei:persName[not(@type)]/tei:surname"/>
        </xsl:call-template>
        <xsl:text>,</xsl:text>

        <!-- Vorname -->
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text" select="tei:persName[not(@type)]/tei:forename"/>
        </xsl:call-template>
        <xsl:text>,</xsl:text>

        <!-- Eigentlicher Name -->
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text" select="tei:persName[@type='eigentlich']/tei:name"/>
        </xsl:call-template>
        <xsl:text>,</xsl:text>

        <!-- GND -->
        <xsl:value-of select="tei:idno[@type='gnd']"/>
        <xsl:text>,</xsl:text>

        <!-- Wikidata -->
        <xsl:value-of select="tei:idno[@type='wikidata']"/>
        <xsl:text>,</xsl:text>

        <!-- Geburtsjahr -->
        <xsl:value-of select="tei:birth/@when"/>
        <xsl:text>,</xsl:text>

        <!-- Sterbejahr -->
        <xsl:value-of select="tei:death/@when"/>
        <xsl:text>,</xsl:text>

        <!-- Notiz (escaped) -->
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text" select="normalize-space(tei:note)"/>
        </xsl:call-template>
        <xsl:text>,</xsl:text>

        <!-- Seiten (mehrere biblScope zusammenfügen) -->
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text">
                <xsl:for-each select="tei:bibl/tei:biblScope[@unit='page']">
                    <xsl:value-of select="@n"/>
                    <xsl:if test="position() != last()">
                        <xsl:text>; </xsl:text>
                    </xsl:if>
                </xsl:for-each>
            </xsl:with-param>
        </xsl:call-template>

        <!-- Zeilenumbruch -->
        <xsl:text>&#10;</xsl:text>
    </xsl:template>

    <!-- CSV Escape Template -->
    <xsl:template name="escape-csv">
        <xsl:param name="text"/>
        <xsl:variable name="clean-text" select="normalize-space($text)"/>

        <xsl:choose>
            <!-- Wenn Text Komma, Anführungszeichen oder Zeilenumbruch enthält, in Anführungszeichen setzen -->
            <xsl:when test="contains($clean-text, ',') or contains($clean-text, '&quot;') or contains($clean-text, '&#10;')">
                <xsl:text>"</xsl:text>
                <xsl:call-template name="escape-quotes">
                    <xsl:with-param name="text" select="$clean-text"/>
                </xsl:call-template>
                <xsl:text>"</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="$clean-text"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- Escape Quotes Template (Anführungszeichen verdoppeln) -->
    <xsl:template name="escape-quotes">
        <xsl:param name="text"/>
        <xsl:choose>
            <xsl:when test="contains($text, '&quot;')">
                <xsl:value-of select="substring-before($text, '&quot;')"/>
                <xsl:text>""</xsl:text>
                <xsl:call-template name="escape-quotes">
                    <xsl:with-param name="text" select="substring-after($text, '&quot;')"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="$text"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
