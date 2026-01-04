"use client"

import { ReactNode } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Card, CardContent } from "@/components/ui/card"

interface ResponsiveTableProps {
  headers: Array<{
    key: string
    label: string
    width?: string
    minWidth?: string
    className?: string
  }>
  data: Array<Record<string, any>>
  renderCell: (item: Record<string, any>, key: string) => ReactNode
  mobileCardRenderer?: (item: Record<string, any>) => ReactNode
  keyField?: string
}

export function ResponsiveTable({
  headers,
  data,
  renderCell,
  mobileCardRenderer,
  keyField = "id"
}: ResponsiveTableProps) {
  return (
    <>
      {/* Desktop Table View */}
      <div className="hidden md:block border rounded-lg overflow-hidden">
        <Table className="w-full">
          <TableHeader>
            <TableRow>
              {headers.map((header) => (
                <TableHead
                  key={header.key}
                  className={header.width ? `${header.width} ${header.minWidth ? `min-w-[${header.minWidth}]` : ''} ${header.className || ''}` : header.className}
                >
                  {header.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((item) => (
              <TableRow key={item[keyField]}>
                {headers.map((header) => (
                  <TableCell key={header.key} className="break-words">
                    {renderCell(item, header.key)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden space-y-4">
        {data.map((item) => (
          <Card key={item[keyField]}>
            <CardContent className="p-4">
              {mobileCardRenderer ? mobileCardRenderer(item) : (
                <div className="space-y-2">
                  {headers.map((header) => (
                    <div key={header.key} className="flex justify-between items-center">
                      <span className="font-medium text-sm text-muted-foreground">
                        {header.label}:
                      </span>
                      <span className="text-sm break-words max-w-[60%]">
                        {renderCell(item, header.key)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}














