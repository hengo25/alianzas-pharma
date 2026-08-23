    def promocion_esta_vigente(item):

        # -------------------------------------------------
        # DEBE ESTAR ACTIVADA
        # -------------------------------------------------

        if not item.get(
            "activo",
            False
        ):

            return False


        fecha_inicio = str(
            item.get(
                "fecha_inicio",
                ""
            )
        ).strip()


        fecha_fin = str(
            item.get(
                "fecha_fin",
                ""
            )
        ).strip()


        # -------------------------------------------------
        # CONVERTIR FECHA
        # ACEPTA:
        # 2026-08-24
        # 24/08/2026
        # -------------------------------------------------

        def convertir_fecha(valor):

            if not valor:

                return None


            formatos = [
                "%Y-%m-%d",
                "%d/%m/%Y"
            ]


            for formato in formatos:

                try:

                    return datetime.strptime(
                        valor,
                        formato
                    ).date()

                except ValueError:

                    continue


            return None


        # -------------------------------------------------
        # VALIDAR FECHA DE INICIO
        # -------------------------------------------------

        if fecha_inicio:

            inicio = convertir_fecha(
                fecha_inicio
            )


            if not inicio:

                return False


            if hoy_colombia < inicio:

                return False


        # -------------------------------------------------
        # VALIDAR FECHA FINAL
        # -------------------------------------------------

        if fecha_fin:

            fin = convertir_fecha(
                fecha_fin
            )


            if not fin:

                return False


            if hoy_colombia > fin:

                return False


        return True
