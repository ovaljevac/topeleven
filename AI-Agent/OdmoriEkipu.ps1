param(
    [ValidateSet('GK', 'DL', 'DC1', 'DC2', 'DR', 'DMC', 'MC1', 'MC2', 'AML', 'AMR', 'ST', 'DL_2', 'ST_2', 'AMR_2', 'AML_2')]
    [string]$TeamRestStart = 'GK'
)

& (Join-Path $PSScriptRoot 'TopElevenAgent.ps1') -Mode OdmoriEkipu -TeamRestStart $TeamRestStart
