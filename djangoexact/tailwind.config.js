/** @type {import('tailwindcss').Config} */
module.exports = {
	content: ["./blog/**/*.{html,js}"],
	darkMode: "class",
	theme: {
		extend: {},
	},
	plugins: [require("@tailwindcss/typography")],
};
