<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs tei"
    version="3.0">

    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

    <!-- Load external listperson.xml from PMB and rename to pmblistperson -->
    <xsl:variable name="pmb-listperson" select="doc('./../data/indices/pmblistperson.xml')"/>
    <xsl:key name="pmb-match" match="tei:person" use="tei:idno[@subtype='ansorge']"/>

    <!-- Identity template -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- Process each person element in the local listperson -->
    <xsl:template match="tei:person">
        <xsl:variable name="current-xmlid" select="@xml:id"/>
        <xsl:variable name="current-idno" select="concat('https://conrad-ansorge.github.io/ansorge-static/', $current-xmlid, '.html')"/>

        <!-- Preserve original note and bibl elements from local listperson -->
        <xsl:variable name="original-notes" select="tei:note"/>
        <xsl:variable name="original-bibls" select="tei:bibl"/>

        <!-- Try to find matching person in PMB listperson by idno subtype="ansorge" -->
        <xsl:variable name="pmb-person" select="key('pmb-match', $current-idno, $pmb-listperson)"/>

        
            <xsl:element name="person" namespace="http://www.tei-c.org/ns/1.0">
            <!-- Ensure xml:id has "ansorge_" prefix -->
            <xsl:attribute name="xml:id">
                
                    
                        <xsl:value-of select="$current-xmlid"/>
                    
                    
                
            </xsl:attribute>

            <!-- Copy other attributes from local person -->
            <xsl:apply-templates select="@*[not(name()='xml:id')]"/>

            <xsl:choose>
                <!-- If match found in PMB, merge PMB data with local data -->
                <xsl:when test="$pmb-person">
                    <!-- Copy all child elements from PMB person -->
                    <xsl:apply-templates select="$pmb-person/node()"/>

                    <!-- Add original note elements from local listperson -->
                    <xsl:apply-templates select="$original-notes"/>

                    <!-- Add original bibl elements from local listperson -->
                    <xsl:apply-templates select="$original-bibls"/>
                </xsl:when>

                <!-- If no match found, keep original person data -->
                <xsl:otherwise>
                    <xsl:apply-templates select="node()"/>
                </xsl:otherwise>
            </xsl:choose>
            </xsl:element>
        
        
    </xsl:template>

</xsl:stylesheet>
