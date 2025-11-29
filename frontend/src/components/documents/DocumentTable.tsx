"use client";

import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal, Eye, Download, Trash2, FileText } from 'lucide-react';

interface Document {
  id: string;
  name: string;
  type: string;
  status: 'processing' | 'completed' | 'failed';
  size: string;
  uploadedAt: string;
  progress?: number;
}

interface DocumentTableProps {
  documents: Document[];
  onView?: (document: Document) => void;
  onDownload?: (document: Document) => void;
  onDelete?: (document: Document) => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  onView,
  onDownload,
  onDelete,
}) => {
  const getStatusBadge = (status: Document['status']) => {
    const variants = {
      processing: 'secondary' as const,
      completed: 'default' as const,
      failed: 'destructive' as const,
    };
    return (
      <Badge variant={variants[status]}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const getDocumentIcon = (type: string) => {
    return <FileText className="h-4 w-4" />;
  };

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Uploaded</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => (
            <TableRow key={document.id} className="hover:bg-muted/50">
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  {getDocumentIcon(document.type)}
                  <span className="truncate max-w-[200px]">
                    {document.name}
                  </span>
                </div>
              </TableCell>
              <TableCell>
                <span className="text-sm text-muted-foreground">
                  {document.type.toUpperCase()}
                </span>
              </TableCell>
              <TableCell>
                {getStatusBadge(document.status)}
                {document.progress && document.status === 'processing' && (
                  <div className="mt-1">
                    <div className="w-24 bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${document.progress}%` }}
                      />
                    </div>
                  </div>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {document.size}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {new Date(document.uploadedAt).toLocaleDateString()}
              </TableCell>
              <TableCell className="text-right">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      className="h-8 w-8 p-0 data-[state=open]:bg-muted"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                      <span className="sr-only">Open menu</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-[160px]">
                    <DropdownMenuLabel>Actions</DropdownMenuLabel>
                    <DropdownMenuItem
                      onClick={() => onView?.(document)}
                      className="cursor-pointer"
                    >
                      <Eye className="mr-2 h-4 w-4" />
                      View
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => onDownload?.(document)}
                      className="cursor-pointer"
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Download
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => onDelete?.(document)}
                      className="cursor-pointer text-destructive focus:text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

// Example usage
export const DocumentTableExample: React.FC = () => {
  const sampleDocuments: Document[] = [
    {
      id: '1',
      name: 'Q4_Financial_Report.pdf',
      type: 'pdf',
      status: 'completed',
      size: '2.4 MB',
      uploadedAt: '2024-01-15',
    },
    {
      id: '2',
      name: 'Product_Demo.mp4',
      type: 'video',
      status: 'processing',
      size: '15.7 MB',
      uploadedAt: '2024-01-16',
      progress: 65,
    },
    {
      id: '3',
      name: 'Meeting_Notes.txt',
      type: 'text',
      status: 'failed',
      size: '24 KB',
      uploadedAt: '2024-01-14',
    },
  ];

  const handleView = (document: Document) => {
    console.log('View document:', document);
  };

  const handleDownload = (document: Document) => {
    console.log('Download document:', document);
  };

  const handleDelete = (document: Document) => {
    console.log('Delete document:', document);
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Document Management</h3>
        <p className="text-sm text-muted-foreground">
          View and manage your uploaded documents with shadcn/ui Table component
        </p>
      </div>
      <DocumentTable
        documents={sampleDocuments}
        onView={handleView}
        onDownload={handleDownload}
        onDelete={handleDelete}
      />
    </div>
  );
};

export default DocumentTable;