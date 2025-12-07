<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="tei">

    <xsl:output method="text" encoding="UTF-8"/>

    <!-- Root Template -->
    <xsl:template match="/">
        <!-- CSV Header -->
        <xsl:text>id,surname,forename,birthYear,deathYear,note,pageRefs,fullName</xsl:text>
        <xsl:text>&#10;</xsl:text>

        <!-- Process all persons -->
        <xsl:apply-templates select="//tei:person"/>
    </xsl:template>

    <!-- Person Template -->
    <xsl:template match="tei:person">
        <!-- ID -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="@xml:id"/>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Surname -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="normalize-space(tei:persName[not(@type)]/tei:surname)"/>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Forename -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="normalize-space(tei:persName[not(@type)]/tei:forename)"/>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Birth Year -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="tei:birth/@when"/>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Death Year -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="tei:death/@when"/>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Note (escaped for CSV) -->
        <xsl:text>"</xsl:text>
        <xsl:call-template name="escape-csv">
            <xsl:with-param name="text" select="normalize-space(tei:note)"/>
        </xsl:call-template>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Page References (concatenated) -->
        <xsl:text>"</xsl:text>
        <xsl:for-each select="tei:bibl/tei:biblScope[@unit='page']">
            <xsl:value-of select="@n"/>
            <xsl:if test="position() != last()">
                <xsl:text>; </xsl:text>
            </xsl:if>
        </xsl:for-each>
        <xsl:text>"</xsl:text>
        <xsl:text>,</xsl:text>

        <!-- Full Name (for better lobid matching) -->
        <xsl:text>"</xsl:text>
        <xsl:value-of select="normalize-space(concat(tei:persName[not(@type)]/tei:forename, ' ', tei:persName[not(@type)]/tei:surname))"/>
        <xsl:text>"</xsl:text>

        <!-- New line -->
        <xsl:text>&#10;</xsl:text>
    </xsl:template>

    <!-- Template to escape quotes in CSV fields -->
    <xsl:template name="escape-csv">
        <xsl:param name="text"/>
        <xsl:value-of select="replace($text, '&quot;', '&quot;&quot;')"/>
    </xsl:template>

</xsl:stylesheet>
