import { useState } from 'react';
import { Tab } from '@headlessui/react';
import clsx from 'clsx';
import UploadPanel from '../components/UploadPanel';

export default function UploadPage() {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const tabs = [
    { name: 'XML Files', component: <UploadPanel contentType="xml" /> },
    { name: 'JSON Files', component: <UploadPanel contentType="json" /> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Data</h1>
        <p className="mt-1 text-sm text-gray-600">
          Upload XML or JSON files for validation and ingestion into the graph database.
        </p>
      </div>

      <Tab.Group selectedIndex={selectedIndex} onChange={setSelectedIndex}>
        <Tab.List className="flex space-x-1 rounded-xl bg-blue-900/20 p-1">
          {tabs.map((tab, index) => (
            <Tab
              key={tab.name}
              className={({ selected }) =>
                clsx(
                  'w-full rounded-lg py-2.5 text-sm font-medium leading-5',
                  'ring-white ring-opacity-60 ring-offset-2 ring-offset-blue-400 focus:outline-none focus:ring-2',
                  selected
                    ? 'bg-white text-blue-700 shadow'
                    : 'text-blue-100 hover:bg-white/[0.12] hover:text-white'
                )
              }
            >
              {tab.name}
            </Tab>
          ))}
        </Tab.List>

        <Tab.Panels className="mt-6 w-full">
          {tabs.map((tab, index) => (
            <Tab.Panel key={index} className="w-full">
              {tab.component}
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}