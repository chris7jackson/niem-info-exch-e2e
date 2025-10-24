import { ReactNode, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Head from 'next/head';
import clsx from 'clsx';
import { apiClient } from '@/lib/api';

interface LayoutProps {
  readonly children: ReactNode;
}

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Schemas', href: '/schemas' },
  { name: 'Upload Data', href: '/upload' },
  { name: 'Graph Explorer', href: '/graph' },
  { name: 'Helper Tools', href: '/tools' },
  { name: 'Admin', href: '/admin' },
];

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const [apiVersion, setApiVersion] = useState<string>('unknown');

  useEffect(() => {
    // Fetch API version on mount
    apiClient.getHealth()
      .then(health => {
        setApiVersion(health.api_version);
      })
      .catch(err => {
        console.error('Failed to fetch API version:', err);
        // Keep default 'unknown' on error
      });
  }, []);

  return (
    <>
      <Head>
        <link rel="icon" href="/favicon.png" />
        <title>NIEM Information Exchange</title>
      </Head>
      <div className="min-h-screen flex flex-col bg-gray-50">
      <nav className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 justify-between">
            <div className="flex">
              <div className="flex flex-shrink-0 items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  NIEM Information Exchange
                </h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={clsx(
                      router.pathname === item.href
                        ? 'border-blue-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
                      'inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium'
                    )}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="flex-1 w-full mx-auto max-w-7xl py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {children}
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center text-sm text-gray-500">
            <div>
              <span className="font-medium">NIEM Information Exchange</span>
              {' '}&copy; {new Date().getFullYear()}
            </div>
            <div className="flex gap-4">
              <span>API: v{apiVersion}</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
    </>
  );
}